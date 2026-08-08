"""
LinuxMouseFix - Action Executor v14
Clean Web Browser Zooming (Ctrl + Plus / Ctrl + Minus / Ctrl + 0)
+ Navigation, Workspace Switching, Media Controls, and Window Management.
"""

import time
import logging

try:
    from evdev import ecodes
    HAS_EVDEV = True
except ImportError:
    HAS_EVDEV = False

log = logging.getLogger("LinuxMouseFix.Actions")


class ActionExecutor:
    """Executes system actions via virtual UInput keyboard/mouse events."""

    def __init__(self, uinput=None):
        self.ui = uinput

    def set_uinput(self, ui):
        self.ui = ui

    def execute(self, action_name):
        if not self.ui:
            return
        handler = getattr(self, f"_act_{action_name}", None)
        if handler:
            try:
                handler()
            except Exception as e:
                log.error(f"Error executing {action_name}: {e}")

    def _press_keys(self, *keys, delay=0.015):
        if not self.ui:
            return
        for key in keys:
            self.ui.write(ecodes.EV_KEY, key, 1)
        self.ui.syn()
        time.sleep(delay)
        for key in reversed(keys):
            self.ui.write(ecodes.EV_KEY, key, 0)
        self.ui.syn()

    def stop_mac_zoom(self):
        pass

    # ─── Web / Browser Zoom (Ctrl + / Ctrl - / Ctrl 0) ───

    def _act_zoomIn(self):
        """Web Browser Zoom In (Ctrl + Plus)."""
        self._press_keys(ecodes.KEY_LEFTCTRL, ecodes.KEY_EQUAL)

    def _act_zoomOut(self):
        """Web Browser Zoom Out (Ctrl + Minus)."""
        self._press_keys(ecodes.KEY_LEFTCTRL, ecodes.KEY_MINUS)

    def _act_zoomReset(self):
        """Web Browser Zoom Reset (Ctrl + 0)."""
        self._press_keys(ecodes.KEY_LEFTCTRL, ecodes.KEY_0)

    def _act_browserZoomIn(self):
        self._act_zoomIn()

    def _act_browserZoomOut(self):
        self._act_zoomOut()

    def _act_browserZoomReset(self):
        self._act_zoomReset()

    # ─── Navigation ──────────────────────────────────────

    def _act_navigateBack(self):
        self._press_keys(ecodes.KEY_LEFTALT, ecodes.KEY_LEFT)

    def _act_navigateForward(self):
        self._press_keys(ecodes.KEY_LEFTALT, ecodes.KEY_RIGHT)

    # ─── Workspace Switching ─────────────────────────────

    def _act_moveLeftDesktop(self):
        self._press_keys(ecodes.KEY_LEFTMETA, ecodes.KEY_LEFTALT, ecodes.KEY_LEFT)

    def _act_moveRightDesktop(self):
        self._press_keys(ecodes.KEY_LEFTMETA, ecodes.KEY_LEFTALT, ecodes.KEY_RIGHT)

    # ─── Desktop / Mission Control / App Grid ────────────

    def _act_showDesktop(self):
        self._press_keys(ecodes.KEY_LEFTMETA, ecodes.KEY_D)

    def _act_missionControl(self):
        self._press_keys(ecodes.KEY_LEFTMETA)

    def _act_appGrid(self):
        self._press_keys(ecodes.KEY_LEFTMETA, ecodes.KEY_A)

    # ─── Mouse Actions ───────────────────────────────────

    def _act_middleClick(self):
        if not self.ui:
            return
        self.ui.write(ecodes.EV_KEY, ecodes.BTN_MIDDLE, 1)
        self.ui.syn()
        time.sleep(0.01)
        self.ui.write(ecodes.EV_KEY, ecodes.BTN_MIDDLE, 0)
        self.ui.syn()

    # ─── Media Controls ──────────────────────────────────

    def _act_volumeUp(self):
        self._press_keys(ecodes.KEY_VOLUMEUP)

    def _act_volumeDown(self):
        self._press_keys(ecodes.KEY_VOLUMEDOWN)

    def _act_playPause(self):
        self._press_keys(ecodes.KEY_PLAYPAUSE)

    def _act_nextTrack(self):
        self._press_keys(ecodes.KEY_NEXTSONG)

    def _act_prevTrack(self):
        self._press_keys(ecodes.KEY_PREVIOUSSONG)

    # ─── Window Management ───────────────────────────────

    def _act_closeWindow(self):
        self._press_keys(ecodes.KEY_LEFTALT, ecodes.KEY_F4)

    def _act_minimizeWindow(self):
        self._press_keys(ecodes.KEY_LEFTMETA, ecodes.KEY_H)

    # ─── Screenshots ─────────────────────────────────────

    def _act_screenshotArea(self):
        """Ubuntu GNOME Dahili Çift Monitör Destekli Ekran Görüntüsü Aracı."""
        self._press_keys(ecodes.KEY_SYSRQ)

    def _act_screenshotFull(self):
        self._press_keys(ecodes.KEY_LEFTSHIFT, ecodes.KEY_SYSRQ)

    # ─── Tab Management ──────────────────────────────────

    def _act_tabNext(self):
        self._press_keys(ecodes.KEY_LEFTCTRL, ecodes.KEY_TAB)

    def _act_tabPrev(self):
        self._press_keys(ecodes.KEY_LEFTCTRL, ecodes.KEY_LEFTSHIFT, ecodes.KEY_TAB)

    def _act_tabClose(self):
        self._press_keys(ecodes.KEY_LEFTCTRL, ecodes.KEY_W)

    # ─── Clipboard ───────────────────────────────────────

    def _act_copy(self):
        self._press_keys(ecodes.KEY_LEFTCTRL, ecodes.KEY_C)

    def _act_paste(self):
        self._press_keys(ecodes.KEY_LEFTCTRL, ecodes.KEY_V)

    def _act_undo(self):
        self._press_keys(ecodes.KEY_LEFTCTRL, ecodes.KEY_Z)

    def _act_redo(self):
        self._press_keys(ecodes.KEY_LEFTCTRL, ecodes.KEY_LEFTSHIFT, ecodes.KEY_Z)

    # ─── No-ops ──────────────────────────────────────────

    def _act_scrollContinuous(self):
        pass

    def _act_none(self):
        pass


actions = ActionExecutor()
