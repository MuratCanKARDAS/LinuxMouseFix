"""
LinuxMouseFix - Input Engine v6
Smooth, fine-tuned 2D Pan / Scroll Dragging with configurable sensitivity (5-100 px/notch),
hi-res scroll synchronization, and key-repeat handling.
"""

import threading
import time
import logging
import subprocess
import os
import ctypes

try:
    from gi.repository import GLib
    HAS_GLIB = True
except Exception:
    HAS_GLIB = False

try:
    import evdev
    from evdev import ecodes, UInput, InputDevice
    HAS_EVDEV = True
except ImportError:
    HAS_EVDEV = False

from config import config
from actions import actions

log = logging.getLogger("LinuxMouseFix.Engine")

BUTTON_MAP = {
    ecodes.BTN_LEFT: 1,
    ecodes.BTN_RIGHT: 2,
    ecodes.BTN_MIDDLE: 3,
    ecodes.BTN_SIDE: 4,
    ecodes.BTN_EXTRA: 5,
}

try:
    BUTTON_MAP[ecodes.BTN_FORWARD] = 5
    BUTTON_MAP[ecodes.BTN_BACK] = 4
except AttributeError:
    pass

EVDEV_BUTTON_NAMES = {
    ecodes.BTN_LEFT:   "Sol Tık",
    ecodes.BTN_RIGHT:  "Sağ Tık",
    ecodes.BTN_MIDDLE: "Orta Buton",
    ecodes.BTN_SIDE:   "Yan Geri (BTN_SIDE)",
    ecodes.BTN_EXTRA:  "Yan İleri (BTN_EXTRA)",
}


def check_permissions():
    """Check if /dev/uinput and /dev/input/event* are accessible."""
    if not HAS_EVDEV:
        return False, "evdev Python modülü yüklenmemiş."
    
    if not os.access("/dev/uinput", os.W_OK):
        return False, "/dev/uinput yazma izni yok."
    
    devs = evdev.list_devices()
    if not devs:
        return False, "/dev/input/event* okuma izni yok."
    
    return True, "İzinler tamam."


def detect_mouse_device():
    """Find the first real mouse device (ignoring touchpads)."""
    if not HAS_EVDEV:
        return None, [], {}

    for path in evdev.list_devices():
        try:
            dev = InputDevice(path)
            caps = dev.capabilities()
            
            if ecodes.EV_REL in caps and ecodes.EV_KEY in caps:
                keys = caps[ecodes.EV_KEY]
                
                if ecodes.BTN_LEFT in keys:
                    if "LinuxMouseFix" in dev.name or "Virtual" in dev.name:
                        continue
                    
                    if ecodes.BTN_TOOL_FINGER in keys or ecodes.EV_ABS in caps:
                        continue

                    detected_btns = []
                    for code, name in sorted(EVDEV_BUTTON_NAMES.items()):
                        if code in keys:
                            logical = BUTTON_MAP.get(code, code)
                            detected_btns.append({
                                "code": code,
                                "logical": logical,
                                "name": name,
                            })

                    rels = caps.get(ecodes.EV_REL, [])
                    has_wheel = ecodes.REL_WHEEL in rels
                    has_hwheel = ecodes.REL_HWHEEL in rels
                    has_hires = ecodes.REL_WHEEL_HI_RES in rels if hasattr(ecodes, 'REL_WHEEL_HI_RES') else False

                    return dev, detected_btns, {
                        "wheel": has_wheel,
                        "hwheel": has_hwheel,
                        "hires": has_hires,
                    }
        except Exception:
            continue
    return None, [], {}


def get_screen_size():
    """Get screen resolution."""
    try:
        output = subprocess.check_output(
            ["xdpyinfo"], stderr=subprocess.DEVNULL
        ).decode()
        for line in output.split('\n'):
            if 'dimensions:' in line:
                dims = line.split()[1]
                w, h = dims.split('x')
                return int(w), int(h)
    except Exception:
        pass

    try:
        output = subprocess.check_output(
            ["xrandr", "--current"], stderr=subprocess.DEVNULL
        ).decode()
        for line in output.split('\n'):
            if ' connected' in line and 'x' in line:
                for part in line.split():
                    if 'x' in part and '+' in part:
                        res = part.split('+')[0]
                        w, h = res.split('x')
                        return int(w), int(h)
    except Exception:
        pass

    return 1920, 1080


class MouseEngine(threading.Thread):
    """
    Input interception engine supporting:
    - 2D Pan / Scroll Dragging (Excel / Browser 2-axis panning)
    - Configurable Pan Sensitivity (5 to 100 px / notch)
    - Hi-Res & Standard Scroll Event Emission
    - EV_SYN event sync
    - Touchpad exclusion
    - Button click / drag / scroll-while-holding gestures
    - Hot corner tracking
    """

    def __init__(self):
        super().__init__(name="MouseEngine")
        self.daemon = True
        self._running = False
        self._mouse = None
        self._ui = None

        self._pressed_buttons = {}
        
        self._cursor_x = 0
        self._cursor_y = 0
        self._screen_w = 1920
        self._screen_h = 1080
        self._hot_corner_active = None
        self._hot_corner_timer = None
        self._hot_corner_cooldown = 0

        self._status_callback = None
        self._device_info_callback = None
        self._listen_callback = None

        self._inertia_thread = None
        self._inertia_active = False

    @property
    def running(self):
        return self._running

    def set_status_callback(self, callback):
        self._status_callback = callback

    def set_device_info_callback(self, callback):
        self._device_info_callback = callback

    def start_listening_button(self, callback):
        self._listen_callback = callback

    def _notify_status(self, running, message=""):
        if self._status_callback:
            try:
                self._status_callback(running, message)
            except Exception:
                pass

    def _notify_device_info(self, name, buttons, caps):
        if self._device_info_callback:
            try:
                self._device_info_callback(name, buttons, caps)
            except Exception:
                pass

    def run(self):
        if not HAS_EVDEV:
            self._notify_status(False, "evdev modülü bulunamadı")
            return

        ok, perm_msg = check_permissions()
        if not ok:
            self._notify_status(False, perm_msg)
            return

        dev, detected_btns, caps = detect_mouse_device()
        if dev:
            self._notify_device_info(dev.name, detected_btns, caps)
            config.detected_device = dev.name
            config.detected_buttons = detected_btns
            config.save()
            self._mouse = dev
        else:
            self._notify_status(False, "Mouse cihazı bulunamadı (Touchpad göz ardı edildi)")
            return

        self._screen_w, self._screen_h = get_screen_size()
        self._cursor_x = self._screen_w // 2
        self._cursor_y = self._screen_h // 2

        cap = {
            ecodes.EV_REL: [
                ecodes.REL_X, ecodes.REL_Y,
                ecodes.REL_WHEEL, ecodes.REL_HWHEEL,
            ],
            ecodes.EV_KEY: [
                ecodes.BTN_LEFT, ecodes.BTN_RIGHT, ecodes.BTN_MIDDLE,
                ecodes.BTN_SIDE, ecodes.BTN_EXTRA,
                ecodes.KEY_LEFTALT, ecodes.KEY_LEFTCTRL,
                ecodes.KEY_LEFTMETA, ecodes.KEY_LEFTSHIFT,
                ecodes.KEY_LEFT, ecodes.KEY_RIGHT,
                ecodes.KEY_UP, ecodes.KEY_DOWN,
                ecodes.KEY_EQUAL, ecodes.KEY_MINUS, ecodes.KEY_0,
                ecodes.KEY_KPPLUS, ecodes.KEY_KPMINUS,
                ecodes.KEY_A, ecodes.KEY_D, ecodes.KEY_H,
                ecodes.KEY_W, ecodes.KEY_C, ecodes.KEY_V, ecodes.KEY_Z,
                ecodes.KEY_F4, ecodes.KEY_TAB,
                ecodes.KEY_VOLUMEUP, ecodes.KEY_VOLUMEDOWN,
                ecodes.KEY_PLAYPAUSE, ecodes.KEY_NEXTSONG, ecodes.KEY_PREVIOUSSONG,
                ecodes.KEY_SYSRQ,
            ],
        }

        try:
            if hasattr(ecodes, 'REL_WHEEL_HI_RES'):
                cap[ecodes.EV_REL].append(ecodes.REL_WHEEL_HI_RES)
            if hasattr(ecodes, 'REL_HWHEEL_HI_RES'):
                cap[ecodes.EV_REL].append(ecodes.REL_HWHEEL_HI_RES)
        except AttributeError:
            pass

        try:
            self._ui = UInput(cap, name="LinuxMouseFix-Virtual", version=0x6)
        except Exception as e:
            self._notify_status(False, f"UInput hatası: {e}")
            return

        actions.set_uinput(self._ui)

        try:
            self._mouse.grab()
        except Exception as e:
            self._notify_status(False, f"Mouse yakalanamadı: {e}")
            self._ui.close()
            return

        self._running = True
        self._notify_status(True, f"Aktif — {self._mouse.name}")
        log.info(f"Engine running on {self._mouse.name}")

        # Start macOS-style Hot Corners via GLib main loop
        self._start_hot_corners()

        try:
            for ev in self._mouse.read_loop():
                if not self._running:
                    break
                self._process_event(ev)
        except OSError as e:
            if self._running:
                self._notify_status(False, f"Cihaz koptu: {e}")
        except Exception as e:
            log.error(f"Loop error: {e}")
        finally:
            self._cleanup()

    def _process_event(self, ev):
        if not config.enabled:
            self._passthrough(ev)
            if ev.type == ecodes.EV_REL:
                self._track_cursor(ev)
            return

        if ev.type == ecodes.EV_KEY:
            self._handle_button(ev)
        elif ev.type == ecodes.EV_REL:
            self._handle_rel(ev)
        else:
            self._passthrough(ev)

    def _stop_inertia(self):
        self._inertia_active = False

    def _start_inertia(self, vx, vy):
        self._stop_inertia()
        self._inertia_active = True

        def inertia_loop():
            inertia_val = getattr(config, "pan_inertia", 65)
            if inertia_val <= 0:
                self._inertia_active = False
                return

            # Dynamic velocity boost (0.25 to 0.75) based on inertia setting
            v_factor = 0.25 + (inertia_val / 100.0) * 0.50
            curr_vx = vx * v_factor
            curr_vy = vy * v_factor

            # Dynamic decay factor per 8ms frame (0.86 to 0.985)
            friction = 0.86 + (inertia_val / 100.0) * 0.125
            dt = 0.008

            hi_res_accum_x = 0.0
            hi_res_accum_y = 0.0
            wheel_accum_x = 0.0
            wheel_accum_y = 0.0

            while self._inertia_active and self._running:
                curr_vx *= friction
                curr_vy *= friction

                if abs(curr_vx) < 10 and abs(curr_vy) < 10:
                    break

                sens = max(1, config.pan_sensitivity)
                inv = -1 if config.pan_invert else 1

                # Calculate sub-pixel hi-res delta (120 units per full notch)
                step_hi_res_y = (curr_vy * dt * 120.0 / sens) * inv
                step_hi_res_x = (curr_vx * dt * 120.0 / sens) * inv

                hi_res_accum_y += step_hi_res_y
                hi_res_accum_x += step_hi_res_x
                wheel_accum_y += step_hi_res_y
                wheel_accum_x += step_hi_res_x

                wrote_event = False

                # Send Hi-Res scroll events continuously for sub-pixel smooth rendering
                if abs(hi_res_accum_y) >= 1.0:
                    val = int(hi_res_accum_y)
                    hi_res_accum_y -= val
                    if self._ui and hasattr(ecodes, 'REL_WHEEL_HI_RES'):
                        self._ui.write(ecodes.EV_REL, ecodes.REL_WHEEL_HI_RES, -val)
                        wrote_event = True

                if abs(hi_res_accum_x) >= 1.0:
                    val = int(hi_res_accum_x)
                    hi_res_accum_x -= val
                    if self._ui and hasattr(ecodes, 'REL_HWHEEL_HI_RES'):
                        self._ui.write(ecodes.EV_REL, ecodes.REL_HWHEEL_HI_RES, val)
                        wrote_event = True

                # Send standard notch REL_WHEEL events for legacy apps when 120 units accumulate
                if abs(wheel_accum_y) >= 120.0:
                    steps = int(wheel_accum_y / 120.0)
                    wheel_accum_y -= steps * 120.0
                    if self._ui:
                        self._ui.write(ecodes.EV_REL, ecodes.REL_WHEEL, -steps)
                        wrote_event = True

                if abs(wheel_accum_x) >= 120.0:
                    steps = int(wheel_accum_x / 120.0)
                    wheel_accum_x -= steps * 120.0
                    if self._ui:
                        self._ui.write(ecodes.EV_REL, ecodes.REL_HWHEEL, steps)
                        wrote_event = True

                if wrote_event and self._ui:
                    self._ui.syn()

                time.sleep(dt)

            self._inertia_active = False

        self._inertia_thread = threading.Thread(target=inertia_loop, daemon=True)
        self._inertia_thread.start()

    def _handle_button(self, ev):
        btn = BUTTON_MAP.get(ev.code, ev.code) # Fallback to ev.code for unknown buttons
        
        # Listen mode intercept
        if getattr(self, "_listen_callback", None) and ev.value == 1:
            cb = self._listen_callback
            self._listen_callback = None
            try:
                name = evdev.ecodes.bytype[evdev.ecodes.EV_KEY].get(ev.code, str(ev.code))
            except Exception:
                name = str(ev.code)
            cb(btn, ev.code, name)
            self._passthrough(ev)
            return

        if btn in (1, 2):  # Never intercept left/right click for normal actions
            self._passthrough(ev)
            return

        has_remap = any(r["button"] == btn for r in config.remaps)
        if not has_remap:
            self._passthrough(ev)
            return

        if ev.value == 1:  # Press
            self._stop_inertia()
            hold_timer = None
            hold_action = config.get_action(btn, "hold")
            if hold_action and hold_action not in ("none", "panScroll"):
                timer = threading.Timer(0.30, self._trigger_hold_action, args=[btn])
                timer.daemon = True
                timer.start()
                hold_timer = timer

            self._pressed_buttons[btn] = {
                "dx": 0, "dy": 0,
                "pan_x": 0, "pan_y": 0,
                "samples": [],
                "triggered": False,
                "evcode": ev.code,
                "last_trigger_time": 0,
                "hold_timer": hold_timer,
            }
        elif ev.value == 2:  # Key repeat while holding
            if btn not in self._pressed_buttons:
                self._pressed_buttons[btn] = {
                    "dx": 0, "dy": 0,
                    "pan_x": 0, "pan_y": 0,
                    "samples": [],
                    "triggered": False,
                    "evcode": ev.code,
                    "last_trigger_time": 0,
                    "hold_timer": None,
                }
        elif ev.value == 0:  # Release
            actions.stop_mac_zoom()
            state = self._pressed_buttons.pop(btn, None)
            if state:
                if state.get("hold_timer"):
                    state["hold_timer"].cancel()

                hold_action = config.get_action(btn, "hold")
                is_pan = (
                    hold_action == "panScroll" or
                    any(r["button"] == btn and r["action"] == "panScroll" for r in config.remaps)
                )

                if state["triggered"] and is_pan:
                    now = time.monotonic()
                    samples = state.get("samples", [])
                    # Only trigger momentum if mouse was actively moving in the last 45ms before release
                    if samples and (now - samples[-1][0]) <= 0.045 and len(samples) >= 2:
                        dt = max(0.010, samples[-1][0] - samples[0][0])
                        total_dx = sum(s[1] for s in samples)
                        total_dy = sum(s[2] for s in samples)
                        vx = total_dx / dt
                        vy = total_dy / dt
                        if abs(vx) > 40 or abs(vy) > 40:
                            self._start_inertia(vx, vy)

                if not state["triggered"]:
                    action = config.get_action(btn, "click")
                    if action and action != "none":
                        actions.execute(action)
                    else:
                        self._ui.write(ecodes.EV_KEY, ev.code, 1)
                        self._ui.syn()
                        time.sleep(0.005)
                        self._ui.write(ecodes.EV_KEY, ev.code, 0)
                        self._ui.syn()

    def _handle_rel(self, ev):
        self._track_cursor(ev)

        # Scroll wheel while holding button
        if ev.code in (ecodes.REL_WHEEL, ecodes.REL_HWHEEL):
            if self._pressed_buttons:
                self._handle_scroll_while_held(ev)
                return
            else:
                self._passthrough(ev)
                return

        # Hi-res wheel from hardware
        try:
            if ev.code in (ecodes.REL_WHEEL_HI_RES, ecodes.REL_HWHEEL_HI_RES):
                if self._pressed_buttons:
                    return
                self._passthrough(ev)
                return
        except AttributeError:
            pass

        # Mouse movement (REL_X, REL_Y)
        if ev.code in (ecodes.REL_X, ecodes.REL_Y):
            if self._pressed_buttons:
                self._handle_drag_or_pan(ev)
                return
            else:
                self._passthrough(ev)
                return

        self._passthrough(ev)

    def _handle_scroll_while_held(self, ev):
        for btn, state in self._pressed_buttons.items():
            if ev.code == ecodes.REL_WHEEL:
                trigger = "scrollUp" if ev.value > 0 else "scrollDown"
                action = config.get_action(btn, trigger)
                if action and action != "none":
                    actions.execute(action)
                    state["triggered"] = True
                    return
        self._passthrough(ev)

    def _trigger_hold_action(self, btn):
        state = self._pressed_buttons.get(btn)
        if state and not state["triggered"]:
            hold_action = config.get_action(btn, "hold")
            if hold_action and hold_action not in ("none", "panScroll"):
                actions.execute(hold_action)
                state["triggered"] = True

    def _handle_drag_or_pan(self, ev):
        """Handle 2D Pan / Scroll Dragging or Directional Gestures."""
        for btn, state in self._pressed_buttons.items():
            hold_action = config.get_action(btn, "hold")
            is_pan = (
                hold_action == "panScroll" or
                any(r["button"] == btn and r["action"] == "panScroll" for r in config.remaps)
            )

            now = time.monotonic()
            dx = ev.value if ev.code == ecodes.REL_X else 0
            dy = ev.value if ev.code == ecodes.REL_Y else 0

            # Store recent samples in ring buffer for precise flick velocity calculation
            samples = state.setdefault("samples", [])
            samples.append((now, dx, dy))
            # Keep only samples within the last 80ms window
            state["samples"] = [s for s in samples if s[0] >= now - 0.080]

            if ev.code == ecodes.REL_X:
                state["dx"] += ev.value
                state["pan_x"] += ev.value
            elif ev.code == ecodes.REL_Y:
                state["dy"] += ev.value
                state["pan_y"] += ev.value

            if abs(state["dx"]) > config.drag_threshold or abs(state["dy"]) > config.drag_threshold:
                if state.get("hold_timer"):
                    state["hold_timer"].cancel()
                    state["hold_timer"] = None

            if is_pan:
                # pan_sensitivity: pixels per full scroll notch (range 5 to 100)
                sens = max(1, config.pan_sensitivity)
                inv = -1 if config.pan_invert else 1

                # Vertical scroll (REL_WHEEL + REL_WHEEL_HI_RES)
                if abs(state["pan_y"]) >= sens:
                    steps = int(state["pan_y"] / sens)
                    direction = -steps * inv

                    self._ui.write(ecodes.EV_REL, ecodes.REL_WHEEL, direction)
                    if hasattr(ecodes, 'REL_WHEEL_HI_RES'):
                        self._ui.write(ecodes.EV_REL, ecodes.REL_WHEEL_HI_RES, direction * 120)
                    self._ui.syn()

                    state["pan_y"] -= steps * sens
                    state["triggered"] = True

                # Horizontal scroll (REL_HWHEEL + REL_HWHEEL_HI_RES)
                if abs(state["pan_x"]) >= sens:
                    steps = int(state["pan_x"] / sens)
                    direction = steps * inv

                    self._ui.write(ecodes.EV_REL, ecodes.REL_HWHEEL, direction)
                    if hasattr(ecodes, 'REL_HWHEEL_HI_RES'):
                        self._ui.write(ecodes.EV_REL, ecodes.REL_HWHEEL_HI_RES, direction * 120)
                    self._ui.syn()

                    state["pan_x"] -= steps * sens
                    state["triggered"] = True

                # PointerFreeze: consume cursor movement
                return

            else:
                threshold = config.drag_threshold

                if not state["triggered"]:
                    trigger = None
                    if state["dx"] > threshold:
                        trigger = "dragRight"
                    elif state["dx"] < -threshold:
                        trigger = "dragLeft"
                    elif state["dy"] > threshold:
                        trigger = "dragDown"
                    elif state["dy"] < -threshold:
                        trigger = "dragUp"

                    if trigger:
                        action = config.get_action(btn, trigger)
                        if action and action != "none":
                            actions.execute(action)
                            state["triggered"] = True
                            state["last_trigger_time"] = time.monotonic()
                            state["last_action"] = action
                            state["dx"] = 0
                            state["dy"] = 0
                else:
                    now = time.monotonic()
                    repeat_threshold = threshold * 2.0
                    if now - state.get("last_trigger_time", 0) > 0.35:
                        trigger = None
                        if abs(state["dx"]) > abs(state["dy"]) and abs(state["dx"]) > repeat_threshold:
                            trigger = "dragRight" if state["dx"] > 0 else "dragLeft"
                        elif abs(state["dy"]) > abs(state["dx"]) and abs(state["dy"]) > repeat_threshold:
                            trigger = "dragDown" if state["dy"] > 0 else "dragUp"

                        if trigger:
                            action = config.get_action(btn, trigger)
                            # Akıllı Geri Dönüş: Eğer yön aksine çevrilirse ve eylem seçilmediyse, pencere/aktivite eylemini kapatır
                            if (not action or action == "none") and state.get("last_action") in ("missionControl", "appGrid", "showDesktop"):
                                action = state["last_action"]

                            if action and action != "none":
                                actions.execute(action)
                                state["last_trigger_time"] = now
                                state["last_action"] = action
                                state["dx"] = 0
                                state["dy"] = 0
                    else:
                        # Cooldown sırasında birikmeyi sıfırla
                        state["dx"] = 0
                        state["dy"] = 0

                    if ev.code == ecodes.REL_Y:
                        for t in ("dragUp", "dragDown"):
                            a = config.get_action(btn, t)
                            if a == "scrollContinuous":
                                direction = -1 if ev.value > 0 else 1
                                self._ui.write(ecodes.EV_REL, ecodes.REL_WHEEL, direction)
                                if hasattr(ecodes, 'REL_WHEEL_HI_RES'):
                                    self._ui.write(ecodes.EV_REL, ecodes.REL_WHEEL_HI_RES, direction * 120)
                                self._ui.syn()
                                break

    def _track_cursor(self, ev):
        """Track cursor for legacy delta accumulation only (not used for hot corners)."""
        if ev.code == ecodes.REL_X:
            self._cursor_x = max(0, min(self._cursor_x + ev.value, self._screen_w - 1))
        elif ev.code == ecodes.REL_Y:
            self._cursor_y = max(0, min(self._cursor_y + ev.value, self._screen_h - 1))

    def _passthrough(self, ev):
        if self._ui:
            self._ui.write(ev.type, ev.code, ev.value)
            if ev.type == ecodes.EV_SYN:
                self._ui.syn()

    def _cleanup(self):
        self._running = False
        if hasattr(self, '_hc_thread') and self._hc_thread:
            self._hc_thread = None
        try:
            if self._mouse:
                self._mouse.ungrab()
        except Exception:
            pass
        try:
            if self._ui:
                self._ui.close()
        except Exception:
            pass
        self._notify_status(False, "Durduruldu")

    def _start_hot_corners(self):
        self._hc_tracker = X11PointerTracker()
        self._hc_active_corner = None
        self._hc_dwell_start = 0
        self._hc_dwell_corner = None
        self._hc_cooldown_until = 0

        if HAS_GLIB:
            GLib.timeout_add(50, self._hot_corner_tick)
            log.info("Hot Corner ticker registered with GLib Main Loop (20Hz)")

    def _hot_corner_tick(self):
        if not self._running:
            if hasattr(self, '_hc_tracker') and self._hc_tracker:
                self._hc_tracker.close()
            return False

        if not config.hot_corner_enabled or not config.enabled:
            self._hc_active_corner = None
            self._hc_dwell_start = 0
            return True

        now = time.monotonic()
        if now < self._hc_cooldown_until:
            return True

        pos, screen = self._hc_tracker.get_pointer_and_screen()
        if pos and screen:
            x, y = pos
            sw, sh = screen
        else:
            x = self._cursor_x
            y = self._cursor_y
            sw = self._screen_w
            sh = self._screen_h

        sz = max(config.hot_corner_size, 10)
        corner = None
        if x <= sz and y <= sz:
            corner = "top_left"
        elif x >= sw - 1 - sz and y <= sz:
            corner = "top_right"
        elif x <= sz and y >= sh - 1 - sz:
            corner = "bottom_left"
        elif x >= sw - 1 - sz and y >= sh - 1 - sz:
            corner = "bottom_right"

        if corner:
            if corner == self._hc_active_corner:
                return True

            if self._hc_dwell_start == 0 or corner != getattr(self, '_hc_dwell_corner', None):
                self._hc_dwell_start = now
                self._hc_dwell_corner = corner

            elapsed_ms = (now - self._hc_dwell_start) * 1000
            if elapsed_ms >= config.hot_corner_delay_ms:
                action = config.get_hot_corner_action(corner)
                if action and action != "none":
                    actions.execute(action)
                    log.info(f"🔥 Hot corner triggered: {corner} -> {action}")
                self._hc_active_corner = corner
                self._hc_cooldown_until = now + 1.2
                self._hc_dwell_start = 0
        else:
            self._hc_active_corner = None
            self._hc_dwell_start = 0
            self._hc_dwell_corner = None

        return True

    def stop(self):
        self._running = False
        if hasattr(self, '_hc_tracker') and self._hc_tracker:
            self._hc_tracker.close()
        if self._mouse:
            try:
                self._mouse.close()
            except Exception:
                pass


class X11PointerTracker:
    def __init__(self):
        self._x11 = None
        self._display = None
        try:
            self._x11 = ctypes.cdll.LoadLibrary("libX11.so.6")
            if hasattr(self._x11, "XInitThreads"):
                self._x11.XInitThreads()
        except Exception as e:
            log.warning(f"Could not load libX11.so.6: {e}")

    def _ensure_display(self):
        if self._display:
            return True
        if not self._x11:
            return False
        try:
            disp_name = os.environ.get("DISPLAY", ":0").encode()
            self._display = self._x11.XOpenDisplay(disp_name)
            if not self._display:
                self._display = self._x11.XOpenDisplay(b":0")
            if not self._display:
                self._display = self._x11.XOpenDisplay(b":1")
        except Exception:
            self._display = None
        return self._display is not None

    def get_pointer_and_screen(self):
        if not self._ensure_display():
            return None, None
        try:
            root = self._x11.XDefaultRootWindow(self._display)
            root_x, root_y = ctypes.c_int(), ctypes.c_int()
            win_x, win_y = ctypes.c_int(), ctypes.c_int()
            mask, child = ctypes.c_uint(), ctypes.c_ulong()

            res = self._x11.XQueryPointer(
                self._display, root,
                ctypes.byref(child), ctypes.byref(child),
                ctypes.byref(root_x), ctypes.byref(root_y),
                ctypes.byref(win_x), ctypes.byref(win_y),
                ctypes.byref(mask)
            )
            sw = self._x11.XDisplayWidth(self._display, 0)
            sh = self._x11.XDisplayHeight(self._display, 0)

            if res != 0:
                return (root_x.value, root_y.value), (sw, sh)
            else:
                self.close()
        except Exception:
            self.close()
        return None, None

    def close(self):
        if self._display and self._x11:
            try:
                self._x11.XCloseDisplay(self._display)
            except Exception:
                pass
        self._display = None


engine = MouseEngine()

