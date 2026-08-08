#!/bin/bash
# Linux Mouse Fix Başlatıcı Script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR" || exit 1

echo "╔══════════════════════════════════════════╗"
echo "║       Linux Mouse Fix v3.0.0             ║"
echo "║  Mac Mouse Fix Port for Ubuntu/Linux     ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Yetki (Zero-Sudo) Kontrolü
if ! groups | grep -q "\binput\b" || [ ! -w /dev/uinput ]; then
    if [ "$EUID" -ne 0 ]; then
        echo "❌ HATA: Fare/Klavye donanımlarına erişim yetkiniz yok!"
        echo "Uygulamanın şifresiz (Zero-Sudo) ve sorunsuz GTK Wayland desteğiyle"
        echo "çalışabilmesi için sistem izinlerinin ayarlanması gereklidir."
        echo ""
        echo "LÜTFEN ŞU ADIMLARI İZLEYİN:"
        echo "1. Terminalde şu komutu çalıştırın:"
        echo "   sudo ./setup_permissions.sh"
        echo "2. İşlem bitince Bilgisayarınızı YENİDEN BAŞLATIN (veya oturumu kapat-aç)."
        echo "3. Yeniden başlattıktan sonra sadece './run.sh' yazarak uygulamayı açın."
        echo ""
        echo "Acil test etmek istiyorsanız 'sudo ./run.sh' ile başlatabilirsiniz (GTK tema uyarıları verebilir)."
        exit 1
    fi
fi

if [ "$EUID" -eq 0 ]; then
    echo "⚠️ UYARI: Uygulama Root (Sudo) olarak başlatıldı!"
    echo "Tavsiye edilen kullanım 'Zero-Sudo' modudur (şifresiz)."
    sudo -E DISPLAY="${DISPLAY:-:0}" XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}" python3 "$SCRIPT_DIR/main.py" "$@"
else
    echo "🚀 Linux Mouse Fix Başlatılıyor (Zero-Sudo Modu Aktif)..."
    python3 "$SCRIPT_DIR/main.py" "$@"
fi
