#!/bin/bash
EXT_DIR="$HOME/.local/share/gnome-shell/extensions/hotcorner-tracker@linuxmousefix.com"

mkdir -p "$EXT_DIR"

cat << 'EOF' > "$EXT_DIR/metadata.json"
{
  "name": "LinuxMouseFix Pointer Tracker",
  "description": "Exposes absolute pointer position for LinuxMouseFix Hot Corners on Wayland.",
  "uuid": "hotcorner-tracker@linuxmousefix.com",
  "shell-version": [
    "45", "46", "47", "48", "49", "50", "51"
  ]
}
EOF

cat << 'EOF' > "$EXT_DIR/extension.js"
import Gio from 'gi://Gio';

const DBusIface = `
<node>
    <interface name="com.linuxmousefix.PointerTracker">
        <method name="GetPosition">
            <arg type="i" name="x" direction="out" />
            <arg type="i" name="y" direction="out" />
        </method>
    </interface>
</node>`;

export default class PointerTrackerExtension {
    enable() {
        try {
            this._dbus = Gio.DBusExportedObject.wrapJSObject(DBusIface, this);
            this._dbus.export(Gio.DBus.session, '/com/linuxmousefix/PointerTracker');
            console.log("[LinuxMouseFix] Extension Enabled");
        } catch (e) {
            console.error("[LinuxMouseFix] Error exporting DBus: " + e);
        }
    }

    disable() {
        if (this._dbus) {
            this._dbus.unexport();
            this._dbus = null;
        }
    }

    GetPosition() {
        try {
            const [x, y] = global.get_pointer();
            return [Math.round(x), Math.round(y)];
        } catch (e) {
            return [-1, -1];
        }
    }
}
EOF

echo "Eklenti dosyaları oluşturuldu."
gnome-extensions install "$EXT_DIR" --force || true
gnome-extensions enable "hotcorner-tracker@linuxmousefix.com"

echo "Eklenti aktif edildi! ÇALIŞMASI İÇİN GNOME OTURUMUNU KAPATIP AÇMANIZ GEREKEBİLİR."
