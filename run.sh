#!/bin/bash
# Linux Mouse Fix Başlatıcı Script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR" || exit 1

echo "╔══════════════════════════════════════════╗"
echo "║       Linux Mouse Fix v3.0.0             ║"
echo "║  Mac Mouse Fix Port for Ubuntu/Linux     ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "🚀 Linux Mouse Fix Başlatılıyor..."

if [ "$EUID" -ne 0 ]; then
    echo "⚠️ UYARI: Donanım seviyesinde fare dinleme için root (sudo) yetkisi gereklidir."
    echo "Sudo yetkisi ile başlatılıyor..."
    sudo python3 "$SCRIPT_DIR/main.py" "$@"
else
    python3 "$SCRIPT_DIR/main.py" "$@"
fi
