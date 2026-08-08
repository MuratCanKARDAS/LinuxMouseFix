#!/bin/bash
# Linux Mouse Fix - Yetkilendirme Scripti
# Bu script, uygulamanın "sudo" olmadan normal kullanıcı olarak çalışabilmesi için
# gerekli /dev/input ve /dev/uinput izinlerini ayarlar.

if [ "$EUID" -ne 0 ]; then
  echo "HATA: Lütfen bu scripti sudo ile çalıştırın!"
  echo "Kullanım: sudo ./setup_permissions.sh"
  exit 1
fi

# Sudo komutunu çalıştıran asıl kullanıcıyı bul
ACTUAL_USER=${SUDO_USER:-$USER}

echo "🔄 1. Kullanıcı '$ACTUAL_USER' 'input' grubuna ekleniyor..."
usermod -aG input "$ACTUAL_USER"

echo "📝 2. udev kuralları oluşturuluyor (/etc/udev/rules.d/99-linuxmousefix.rules)..."
cat << 'EOF' > /etc/udev/rules.d/99-linuxmousefix.rules
# Linux Mouse Fix - Donanım İzin Kuralları

# Fare ve klavye donanımlarını okuma yetkisi
SUBSYSTEM=="input", GROUP="input", MODE="0660"

# Sanal fare/klavye cihazı (uinput) yaratma yetkisi
KERNEL=="uinput", GROUP="input", MODE="0660", OPTIONS+="static_node=uinput"
EOF

echo "⚡ 3. Sistem udev kuralları yeniden yükleniyor..."
udevadm control --reload-rules
udevadm trigger

echo ""
echo "✅ BAŞARILI: Donanım erişim izinleri sisteme tanımlandı."
echo "========================================================================="
echo "⚠️  KRİTİK UYARI: İşletim sisteminin sizi 'input' grubuna dahil edebilmesi"
echo "için BİLGİSAYARI YENİDEN BAŞLATMANIZ veya OTURUMU KAPATIP AÇMANIZ ŞARTTIR."
echo "========================================================================="
echo "Yeniden başlattıktan sonra programı sadece './run.sh' (sudo olmadan) çalıştırabilirsiniz!"
