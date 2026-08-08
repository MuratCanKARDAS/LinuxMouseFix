"""
LinuxMouseFix - Configuration Manager v12
Clean Web Browser Zooming (Ctrl + Plus / Ctrl + Minus / Ctrl + 0).
"""

import os
import json
import copy

CONFIG_DIR = os.path.expanduser("~/.config/LinuxMouseFix")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

TRIGGER_TYPES = {
    "click":      "Tıklama",
    "hold":       "Basılı Tutma (Sürekli 2D Pan)",
    "dragLeft":   "Basılı Tut + Sola Kaydır",
    "dragRight":  "Basılı Tut + Sağa Kaydır",
    "dragUp":     "Basılı Tut + Yukarı Kaydır",
    "dragDown":   "Basılı Tut + Aşağı Kaydır",
    "scrollUp":   "Basılı Tut + Tekerlek Yukarı",
    "scrollDown": "Basılı Tut + Tekerlek Aşağı",
}

ACTIONS = {
    "none":              "Hiçbir Şey",
    "panScroll":         "📜 2D Pan / Sayfa Kaydırma (Excel/Tarayıcı Hem Yatay Hem Dikey)",
    "zoomIn":            "🌐 Web Yakınlaştır (Ctrl+Plus)",
    "zoomOut":           "🌐 Web Uzaklaştır (Ctrl+Minus)",
    "zoomReset":         "🌐 Web Zoom Sıfırla (Ctrl+0)",
    "moveLeftDesktop":   "Sol Masaüstüne Geç",
    "moveRightDesktop":  "Sağ Masaüstüne Geç",
    "navigateBack":      "Geri Git",
    "navigateForward":   "İleri Git",
    "showDesktop":       "Masaüstünü Göster",
    "missionControl":    "Aktiviteleri Göster (Super)",
    "appGrid":           "Uygulama Listesi (Super+A)",
    "middleClick":       "Orta Tık",
    "volumeUp":          "Ses Aç",
    "volumeDown":        "Ses Kıs",
    "playPause":         "Oynat/Duraklat",
    "nextTrack":         "Sonraki Parça",
    "prevTrack":         "Önceki Parça",
    "closeWindow":       "Pencereyi Kapat (Alt+F4)",
    "minimizeWindow":    "Pencereyi Küçült",
    "screenshotArea":    "📸 Ekran Görüntüsü (Alan Seç)",
    "screenshotFull":    "📸 Ekran Görüntüsü (Tüm Ekran)",
    "tabNext":           "Sonraki Sekme (Ctrl+Tab)",
    "tabPrev":           "Önceki Sekme (Ctrl+Shift+Tab)",
    "tabClose":          "Sekmeyi Kapat (Ctrl+W)",
    "copy":              "Kopyala (Ctrl+C)",
    "paste":             "Yapıştır (Ctrl+V)",
    "undo":              "Geri Al (Ctrl+Z)",
    "redo":              "Yinele (Ctrl+Shift+Z)",
}

BUTTON_NAMES = {
    1: "Sol Tık (BTN_LEFT)",
    2: "Sağ Tık (BTN_RIGHT)",
    3: "Orta Buton (BTN_MIDDLE)",
    4: "Yan Buton Geri (BTN_SIDE)",
    5: "Yan Buton İleri (BTN_EXTRA)",
    6: "Buton 6",
    7: "Buton 7",
    8: "Buton 8",
    9: "Buton 9",
}

HOT_CORNER_ACTIONS = {
    "none":            "Kapalı",
    "missionControl":  "Aktiviteleri Göster",
    "appGrid":         "Uygulama Listesi",
    "showDesktop":     "Masaüstünü Göster",
    "moveLeftDesktop": "Sol Masaüstüne Geç",
    "moveRightDesktop":"Sağ Masaüstüne Geç",
}

DEFAULT_REMAPS = []

DEFAULT_HOT_CORNERS = {
    "top_left":     "missionControl",
    "top_right":    "showDesktop",
    "bottom_left":  "none",
    "bottom_right": "appGrid",
}


class Config:
    """Configuration manager."""

    def __init__(self):
        self.enabled = True
        self.autostart = False
        self.drag_threshold = 40
        self.pan_sensitivity = 25
        self.pan_inertia = 65
        self.pan_invert = False
        self.hot_corner_size = 15
        self.hot_corner_enabled = True
        self.hot_corner_delay_ms = 200
        self.remaps = copy.deepcopy(DEFAULT_REMAPS)
        self.hot_corners = copy.deepcopy(DEFAULT_HOT_CORNERS)
        self.detected_device = ""
        self.detected_buttons = []
        self._observers = []
        self.load()

    def add_observer(self, callback):
        self._observers.append(callback)

    def _notify(self):
        for cb in self._observers:
            try:
                cb()
            except Exception:
                pass

    def load(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                self.enabled = data.get("enabled", True)
                self.autostart = data.get("autostart", False)
                self.drag_threshold = data.get("drag_threshold", 40)
                self.pan_sensitivity = data.get("pan_sensitivity", 25)
                self.pan_inertia = data.get("pan_inertia", 65)
                self.pan_invert = data.get("pan_invert", False)
                self.hot_corner_size = data.get("hot_corner_size", 15)
                if self.hot_corner_size < 10:
                    self.hot_corner_size = 15

                self.hot_corner_enabled = data.get("hot_corner_enabled", True)
                self.hot_corner_delay_ms = data.get("hot_corner_delay_ms", 200)
                self.remaps = data.get("remaps", copy.deepcopy(DEFAULT_REMAPS))
                self.hot_corners = data.get("hot_corners", copy.deepcopy(DEFAULT_HOT_CORNERS))

                # Auto-upgrade if all hot corners are set to none
                if all(v == "none" for v in self.hot_corners.values()):
                    self.hot_corners = copy.deepcopy(DEFAULT_HOT_CORNERS)
                    self.save()

                self.detected_device = data.get("detected_device", "")
                self.detected_buttons = data.get("detected_buttons", [])
            except (json.JSONDecodeError, KeyError):
                self.save()
        else:
            self.save()

    def save(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        data = {
            "enabled": self.enabled,
            "autostart": self.autostart,
            "drag_threshold": self.drag_threshold,
            "pan_sensitivity": self.pan_sensitivity,
            "pan_inertia": self.pan_inertia,
            "pan_invert": self.pan_invert,
            "hot_corner_size": self.hot_corner_size,
            "hot_corner_enabled": self.hot_corner_enabled,
            "hot_corner_delay_ms": self.hot_corner_delay_ms,
            "remaps": self.remaps,
            "hot_corners": self.hot_corners,
            "detected_device": self.detected_device,
            "detected_buttons": self.detected_buttons,
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        self._update_autostart_desktop()
        self._notify()

    def _update_autostart_desktop(self):
        autostart_dir = os.path.expanduser("~/.config/autostart")
        desktop_file = os.path.join(autostart_dir, "linuxmousefix.desktop")
        
        if self.autostart:
            os.makedirs(autostart_dir, exist_ok=True)
            current_dir = os.path.dirname(os.path.abspath(__file__))
            run_script = os.path.join(current_dir, "run.sh")
            
            content = f"[Desktop Entry]\nType=Application\nExec={run_script}\nHidden=false\nNoDisplay=false\nX-GNOME-Autostart-enabled=true\nName=Linux Mouse Fix\nComment=Mac-like gestures for Linux\nIcon=input-mouse\n"
            try:
                with open(desktop_file, "w") as f:
                    f.write(content)
            except Exception:
                pass
        else:
            if os.path.exists(desktop_file):
                try:
                    os.remove(desktop_file)
                except Exception:
                    pass

    def add_remap(self, button, trigger, action):
        for r in self.remaps:
            if r["button"] == button and r["trigger"] == trigger:
                r["action"] = action
                self.save()
                return
        self.remaps.append({"button": button, "trigger": trigger, "action": action})
        self.save()

    def remove_remap(self, index):
        if 0 <= index < len(self.remaps):
            self.remaps.pop(index)
            self.save()

    def update_remap_action(self, index, new_action):
        if 0 <= index < len(self.remaps):
            self.remaps[index]["action"] = new_action
            self.save()

    def get_action(self, button, trigger):
        for r in self.remaps:
            if r["button"] == button and r["trigger"] == trigger:
                return r["action"]
        return None

    def set_hot_corner(self, corner, action):
        self.hot_corners[corner] = action
        self.save()

    def get_hot_corner_action(self, corner):
        return self.hot_corners.get(corner, "none")

    def reset_to_defaults(self):
        self.remaps = copy.deepcopy(DEFAULT_REMAPS)
        self.hot_corners = copy.deepcopy(DEFAULT_HOT_CORNERS)
        self.enabled = True
        self.drag_threshold = 40
        self.pan_sensitivity = 25
        self.pan_inertia = 65
        self.pan_invert = False
        self.hot_corner_enabled = True
        self.hot_corner_size = 15
        self.hot_corner_delay_ms = 200
        self.save()


config = Config()
