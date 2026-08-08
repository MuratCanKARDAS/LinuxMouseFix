#!/bin/bash
# Linux Mouse Fix - Permission Setup Script
# Configures udev rules so LinuxMouseFix can access /dev/input/event* and /dev/uinput
# without needing root/sudo every time.

set -e

echo "=== LinuxMouseFix İzin Yapılandırması ==="

# 1. Ensure uinput kernel module is loaded
modprobe uinput 2>/dev/null || true
if ! grep -q "^uinput" /etc/modules-load.d/uinput.conf 2>/dev/null; then
    echo "uinput" >> /etc/modules-load.d/uinput.conf 2>/dev/null || true
fi

# 2. Add udev rule for uinput and input event devices
UDEV_RULE_FILE="/etc/udev/rules.d/99-linuxmousefix.rules"

cat << 'EOF' > "$UDEV_RULE_FILE"
# LinuxMouseFix permissions
KERNEL=="uinput", MODE="0666", OPTIONS+="static_node=uinput"
KERNEL=="event*", SUBSYSTEM=="input", MODE="0666"
EOF

echo "✅ udev kuralı oluşturuldu: $UDEV_RULE_FILE"

# 3. Reload udev rules and trigger
udevadm control --reload-rules 2>/dev/null || true
udevadm trigger 2>/dev/null || true

# 4. Set current runtime permissions immediately
chmod 666 /dev/uinput 2>/dev/null || true
chmod 666 /dev/input/event* 2>/dev/null || true

# 5. Add user to input group if user specified
TARGET_USER="${SUDO_USER:-$1}"
if [ -n "$TARGET_USER" ] && id "$TARGET_USER" &>/dev/null; then
    usermod -aG input "$TARGET_USER" 2>/dev/null || true
    echo "✅ Kullanıcı '$TARGET_USER' input grubuna eklendi."
fi

echo "=== İzinler Başarıyla Yapılandırıldı ==="
