# 🖱️ Linux Mouse Fix v3.0.0

**Linux Mouse Fix** is a feature-rich, high-performance Mac Mouse Fix port for Ubuntu and Linux desktop environments (GNOME / Wayland / X11). Built using Python, `evdev`, GTK4, and Libadwaita.

---

## ✨ Features

- 🎯 **Dynamic Button Listening (Listen Mode):** Automatically detects any physical mouse button (including 30+ button gaming mice like Pusat V11) without hardcoded keymaps.
- 📜 **2D Pan & Drag Scrolling:** Smooth two-dimensional document pan scrolling (horizontal and vertical) across Excel, Web Browsers, and IDEs.
- 📸 **Smart Screenshot Integration:** One-touch / Hold-to-capture screenshot tool (supports Ubuntu GNOME Native & Flameshot).
- 🔄 **Auto-Reversing Gestures:** Hold button + drag UP to open GNOME Activities Overview, drag DOWN to return to normal desktop state seamlessly.
- 🌐 **Web Browser Zooming:** Smooth zoom control via shortcuts (`Ctrl +` / `Ctrl -` / `Ctrl 0`).
- 🎨 **Modern GTK4 / Libadwaita Interface:** Premium native UI with dark theme, dynamic button recognition, and real-time status indicators.

---

## 🚀 Quick Start

### 1. Requirements
- Python 3.10+
- `python3-evdev`
- `PyGObject` (GTK4 & Libadwaita)

Install required dependencies on Ubuntu / Debian:
```bash
sudo apt update
sudo apt install -y python3-evdev python3-gi python3-gi-cairo libgtk-4-dev libadwaita-1-0
```

### 2. Running Linux Mouse Fix
Because low-level hardware event interception via `/dev/input/` requires device access permissions, run the application with root privileges:

```bash
./run.sh
```
*or directly:*
```bash
sudo python3 main.py
```

---

## 🛠️ Project Structure

```
├── main.py                 # Application entry point
├── engine.py               # Core evdev event loop & gesture interceptor
├── ui_app.py               # Modern GTK4 / Libadwaita user interface
├── config.py               # JSON settings & custom button remaps manager
├── actions.py              # Keyboard & system action simulator
├── setup_permissions.sh    # Optional udev rules configuration script
├── linuxmousefix.desktop   # System desktop entry file
├── run.sh                  # Launcher script
└── README.md
```

---

## 👤 Author

**Murat Can KARDAS**  
- GitHub: [@MuratCanKARDAS](https://github.com/MuratCanKARDAS)

---

## 📄 License
MIT License. Free for open source software & community contributions.
