"""
LinuxMouseFix — GTK4/Adwaita UI v6
Fixes GTK title markup warnings, supports 2D Pan Sensitivity adjustment (5 to 100 range),
Pan Invert option, permission banner with pkexec installer, and device detection.
"""
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib, Gdk
import sys
import os
import subprocess
from config import (config, TRIGGER_TYPES, ACTIONS, BUTTON_NAMES,
                    HOT_CORNER_ACTIONS)
from engine import check_permissions


class RemapRow(Adw.ActionRow):
    def __init__(self, index, remap_data, on_delete, on_action_changed):
        super().__init__()
        self._index = index
        self._on_delete = on_delete
        self._on_action_changed = on_action_changed
        btn = remap_data["button"]
        trigger = remap_data["trigger"]
        action = remap_data["action"]
        self.set_title(BUTTON_NAMES.get(btn, f"Özel Buton {btn}"))
        self.set_subtitle(TRIGGER_TYPES.get(trigger, trigger))

        badge = Gtk.Label(label=str(btn))
        badge.set_size_request(36, 36)
        badge.add_css_class("remap-badge")
        badge.add_css_class(f"badge-btn-{btn}")
        self.add_prefix(badge)

        icon_map = {
            "click": "input-mouse-symbolic",
            "hold": "pan-up-symbolic",
            "dragLeft": "go-previous-symbolic",
            "dragRight": "go-next-symbolic",
            "dragUp": "go-up-symbolic",
            "dragDown": "go-down-symbolic",
            "scrollUp": "zoom-in-symbolic",
            "scrollDown": "zoom-out-symbolic"
        }
        di = Gtk.Image.new_from_icon_name(icon_map.get(trigger, "input-mouse-symbolic"))
        di.add_css_class("dim-label")
        self.add_prefix(di)

        arrow = Gtk.Label(label="→")
        arrow.add_css_class("dim-label")
        arrow.set_margin_start(8)
        arrow.set_margin_end(4)
        arrow.set_valign(Gtk.Align.CENTER)
        self.add_suffix(arrow)

        action_model = Gtk.StringList()
        self._action_keys = list(ACTIONS.keys())
        for key in self._action_keys:
            action_model.append(ACTIONS[key])
        dropdown = Gtk.DropDown(model=action_model)
        dropdown.set_valign(Gtk.Align.CENTER)
        try:
            dropdown.set_selected(self._action_keys.index(action))
        except ValueError:
            pass
        dropdown.connect("notify::selected", self._on_dd)
        self.add_suffix(dropdown)

        db = Gtk.Button(icon_name="edit-delete-symbolic")
        db.set_valign(Gtk.Align.CENTER)
        db.add_css_class("flat")
        db.add_css_class("error")
        db.set_tooltip_text("Sil")
        db.connect("clicked", lambda _: self._on_delete(self._index))
        self.add_suffix(db)
        self.set_activatable(False)

    def _on_dd(self, dd, _):
        idx = dd.get_selected()
        if 0 <= idx < len(self._action_keys):
            self._on_action_changed(self._index, self._action_keys[idx])


class AddRemapDialog(Adw.Dialog):
    def __init__(self, on_add):
        super().__init__()
        self._on_add = on_add
        self.set_title("Yeni Atama Ekle")
        self.set_content_width(440)
        self.set_content_height(460)
        tv = Adw.ToolbarView()
        hdr = Adw.HeaderBar()
        hdr.set_show_start_title_buttons(False)
        hdr.set_show_end_title_buttons(False)
        cb = Gtk.Button(label="İptal")
        cb.connect("clicked", lambda _: self.close())
        hdr.pack_start(cb)
        ab = Gtk.Button(label="Ekle")
        ab.add_css_class("suggested-action")
        ab.connect("clicked", self._do_add)
        hdr.pack_end(ab)
        tv.add_top_bar(hdr)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)

        prefs = Adw.PreferencesGroup(title="Yeni Atama")
        
        self._btn_row = Adw.ActionRow(title="Buton", subtitle="Seçilmedi (Tıklayın)")
        self._listen_btn = Gtk.Button(label="🖱️ Fare Tuşuna Bas")
        self._listen_btn.set_valign(Gtk.Align.CENTER)
        self._listen_btn.add_css_class("suggested-action")
        self._listen_btn.connect("clicked", self._on_listen_clicked)
        self._btn_row.add_suffix(self._listen_btn)
        prefs.add(self._btn_row)
        
        self._selected_btn_id = None

        tm = Gtk.StringList()
        self._tvals = list(TRIGGER_TYPES.keys())
        for k in self._tvals:
            tm.append(TRIGGER_TYPES[k])
        self._tr = Adw.ComboRow(title="Tetikleme", model=tm)
        self._tr.set_selected(1)  # Default to hold
        prefs.add(self._tr)

        am = Gtk.StringList()
        self._avals = list(ACTIONS.keys())
        for k in self._avals:
            am.append(ACTIONS[k])
        self._ar = Adw.ComboRow(title="Eylem", model=am)
        self._ar.set_selected(1)  # Default to panScroll
        prefs.add(self._ar)
        box.append(prefs)

        hint = Gtk.Label(label="💡 Örnek: Yan Buton 4 + Basılı Tutma → 2D Pan / Sayfa Kaydırma (Excel/Tarayıcı)")
        hint.set_wrap(True)
        hint.add_css_class("dim-label")
        box.append(hint)

        clamp = Adw.Clamp(maximum_size=420)
        clamp.set_child(box)
        tv.set_content(clamp)
        self.set_child(tv)

    def _on_listen_clicked(self, _):
        self._listen_btn.set_label("Bekleniyor...")
        self._listen_btn.set_sensitive(False)
        try:
            app = Gio.Application.get_default()
            app._engine.start_listening_button(self._on_button_detected)
        except Exception as e:
            self._listen_btn.set_label(f"Hata! {e}")
            self._listen_btn.set_sensitive(True)
            
    def _on_button_detected(self, logical_id, ev_code, name):
        def _update():
            self._selected_btn_id = logical_id
            btn_name = name[0] if isinstance(name, (list, tuple)) else name
            nm = BUTTON_NAMES.get(logical_id, f"{btn_name} (Kod: {ev_code})")
            self._btn_row.set_subtitle(f"Seçilen: Buton {logical_id} — {nm}")
            self._listen_btn.set_label("Yeniden Algıla")
            self._listen_btn.set_sensitive(True)
            self._listen_btn.remove_css_class("suggested-action")
        GLib.idle_add(_update)

    def _do_add(self, _):
        if self._selected_btn_id is None:
            # Geri dönüş değeri (default 4)
            self._selected_btn_id = 4
        b = self._selected_btn_id
        t = self._tvals[self._tr.get_selected()]
        a = self._avals[self._ar.get_selected()]
        self._on_add(b, t, a)
        self.close()


class LinuxMouseFixWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("Linux Mouse Fix")
        self.set_default_size(630, 860)

        tv = Adw.ToolbarView()
        hdr = Adw.HeaderBar()
        hdr.set_title_widget(Adw.WindowTitle(title="Linux Mouse Fix", subtitle="v6.0 — 2D Pan ve Gesture Aracı"))
        menu = Gio.Menu()
        menu.append("Varsayılana Sıfırla", "app.reset")
        menu.append("Hakkında", "app.about")
        hdr.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu))
        tv.add_top_bar(hdr)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        clamp = Adw.Clamp(maximum_size=660)
        self._box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self._box.set_margin_top(20)
        self._box.set_margin_bottom(40)
        self._box.set_margin_start(16)
        self._box.set_margin_end(16)

        # Permission Setup Banner
        self._perm_banner = Adw.Banner()
        self._perm_banner.set_title("⚠️ Mouse erişim izinleri eksik. Motor başlatılamıyor.")
        self._perm_banner.set_button_label("İzinleri Yapılandır")
        self._perm_banner.connect("button-clicked", self._on_fix_permissions)
        self._perm_banner.set_revealed(False)
        self._box.append(self._perm_banner)

        self._build_status()
        self._build_device_info()

        banner = Adw.Banner()
        banner.set_title("💡 Yan butona basıp fareyi gezdirin: Excel ve web sayfalarında hem yatay hem dikey 2D Pan yapın!")
        banner.set_revealed(True)
        self._box.append(banner)

        self._remaps_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._box.append(self._remaps_container)
        self._build_remaps()

        self._build_hot_corners()
        self._build_settings()
        self._build_howto()

        clamp.set_child(self._box)
        scroll.set_child(clamp)
        tv.set_content(scroll)
        self.set_content(tv)

        self.check_perm_status()

    def check_perm_status(self):
        ok, msg = check_permissions()
        if not ok:
            self._perm_banner.set_title(f"⚠️ {msg} Lütfen izinleri yapılandırın.")
            self._perm_banner.set_revealed(True)
        else:
            self._perm_banner.set_revealed(False)

    def _on_fix_permissions(self, _):
        script_path = os.path.join(os.path.dirname(__file__), "setup_permissions.sh")
        user = os.getenv("USER", "")
        cmd = ["pkexec", "bash", script_path, user]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                self.check_perm_status()
                app = self.get_application()
                if app and hasattr(app, "_start_engine"):
                    app._start_engine()
            else:
                dialog = Adw.AlertDialog()
                dialog.set_heading("İzin Yapılandırması Başarısız")
                dialog.set_body(f"Hata: {res.stderr or 'İptal edildi.'}")
                dialog.add_response("ok", "Tamam")
                dialog.present(self)
        except Exception as e:
            dialog = Adw.AlertDialog()
            dialog.set_heading("Hata")
            dialog.set_body(str(e))
            dialog.add_response("ok", "Tamam")
            dialog.present(self)

    def _build_status(self):
        g = Adw.PreferencesGroup(title="Durum")
        self._enable_row = Adw.SwitchRow(title="Motor Aktif", subtitle="Mouse yakalama ve yönlendirme")
        self._enable_row.set_active(config.enabled)
        self._enable_row.connect("notify::active", lambda r, _: (setattr(config, 'enabled', r.get_active()), config.save()))
        g.add(self._enable_row)

        self._status_row = Adw.ActionRow(title="Bağlantı", subtitle="Başlatılıyor...")
        self._status_icon = Gtk.Image.new_from_icon_name("network-offline-symbolic")
        self._status_row.add_prefix(self._status_icon)
        self._status_dot = Gtk.Label(label="●")
        self._status_dot.add_css_class("status-inactive")
        self._status_dot.set_valign(Gtk.Align.CENTER)
        self._status_row.add_suffix(self._status_dot)
        g.add(self._status_row)
        self._box.append(g)

    def _build_device_info(self):
        self._device_group = Adw.PreferencesGroup(title="🖱️ Algılanan Cihaz", description="Otomatik algılanan mouse ve butonları")
        self._device_name_row = Adw.ActionRow(title="Cihaz", subtitle="Algılanıyor...")
        self._device_name_row.add_prefix(Gtk.Image.new_from_icon_name("input-mouse-symbolic"))
        self._device_group.add(self._device_name_row)
        self._device_buttons_row = Adw.ActionRow(title="Butonlar", subtitle="—")
        self._device_buttons_row.add_prefix(Gtk.Image.new_from_icon_name("preferences-desktop-peripherals-symbolic"))
        self._device_group.add(self._device_buttons_row)
        self._device_caps_row = Adw.ActionRow(title="Özellikler", subtitle="—")
        self._device_caps_row.add_prefix(Gtk.Image.new_from_icon_name("dialog-information-symbolic"))
        self._device_group.add(self._device_caps_row)
        self._box.append(self._device_group)

    def _build_remaps(self):
        child = self._remaps_container.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self._remaps_container.remove(child)
            child = nxt

        g = Adw.PreferencesGroup(title="⚡ Buton Atamaları", description="Buton + hareket/tekerlek → eylem")
        ab = Gtk.Button(icon_name="list-add-symbolic")
        ab.add_css_class("flat")
        ab.set_tooltip_text("Yeni atama ekle")
        ab.set_valign(Gtk.Align.CENTER)
        ab.connect("clicked", self._on_add)
        g.set_header_suffix(ab)

        if not config.remaps:
            g.add(Adw.ActionRow(title="Atama yok", subtitle="+ ile ekleyin"))
        else:
            for i, r in enumerate(config.remaps):
                g.add(RemapRow(i, r, self._on_del, self._on_act_change))
        self._remaps_container.append(g)

    def _build_hot_corners(self):
        g = Adw.PreferencesGroup(title="🔲 Hot Corner (Sıcak Köşe)", description="Fareyi köşeye götürünce eylem tetiklenir")

        self._hc_switch = Adw.SwitchRow(title="Hot Corner Aktif")
        self._hc_switch.set_active(config.hot_corner_enabled)
        self._hc_switch.connect("notify::active", lambda r, _: (setattr(config, 'hot_corner_enabled', r.get_active()), config.save()))
        g.add(self._hc_switch)

        corners = [
            ("top_left", "↖ Sol Üst Köşe"),
            ("top_right", "↗ Sağ Üst Köşe"),
            ("bottom_left", "↙ Sol Alt Köşe"),
            ("bottom_right", "↘ Sağ Alt Köşe"),
        ]
        hc_keys = list(HOT_CORNER_ACTIONS.keys())
        for cid, clabel in corners:
            model = Gtk.StringList()
            for k in hc_keys:
                model.append(HOT_CORNER_ACTIONS[k])
            row = Adw.ComboRow(title=clabel, model=model)
            cur = config.get_hot_corner_action(cid)
            try:
                row.set_selected(hc_keys.index(cur))
            except ValueError:
                pass
            row.connect("notify::selected", self._make_hc_handler(cid, hc_keys))
            g.add(row)

        delay_row = Adw.SpinRow.new_with_range(0, 1000, 50)
        delay_row.set_title("Gecikme (ms)")
        delay_row.set_subtitle("Köşede bekleme süresi")
        delay_row.set_value(config.hot_corner_delay_ms)
        delay_row.connect("notify::value", lambda r, _: (setattr(config, 'hot_corner_delay_ms', int(r.get_value())), config.save()))
        g.add(delay_row)

        sz_row = Adw.SpinRow.new_with_range(1, 30, 1)
        sz_row.set_title("Köşe Boyutu (px)")
        sz_row.set_subtitle("Tetikleme alanı piksel genişliği")
        sz_row.set_value(config.hot_corner_size)
        sz_row.connect("notify::value", lambda r, _: (setattr(config, 'hot_corner_size', int(r.get_value())), config.save()))
        g.add(sz_row)

        self._box.append(g)

    def _make_hc_handler(self, corner_id, keys):
        def handler(row, _):
            idx = row.get_selected()
            if 0 <= idx < len(keys):
                config.set_hot_corner(corner_id, keys[idx])
        return handler

    def _build_settings(self):
        g = Adw.PreferencesGroup(title="⚙️ Pan ve Sürükleme Ayarları")

        # Pan Sensitivity (5 to 100 px per notch)
        pan_sens_row = Adw.SpinRow.new_with_range(5, 100, 5)
        pan_sens_row.set_title("2D Pan Kaydırma Hassasiyeti")
        pan_sens_row.set_subtitle("Yüksek Değer = Yavaş/Hassas Kaydırma, Düşük Değer = Hızlı Kaydırma (Piksel/Adım)")
        pan_sens_row.set_value(config.pan_sensitivity)
        pan_sens_row.connect("notify::value", lambda r, _: (setattr(config, 'pan_sensitivity', int(r.get_value())), config.save()))
        g.add(pan_sens_row)

        # Pan Inertia / Momentum Duration (0 to 100)
        pan_ine_row = Adw.SpinRow.new_with_range(0, 100, 5)
        pan_ine_row.set_title("Ataletli Yumuşak Süzülme (Momentum Glide)")
        pan_ine_row.set_subtitle("0 = Anında Dur, 50 = Standart, 70-100 = Uzun ve Akıcı Süzülme")
        pan_ine_row.set_value(config.pan_inertia)
        pan_ine_row.connect("notify::value", lambda r, _: (setattr(config, 'pan_inertia', int(r.get_value())), config.save()))
        g.add(pan_ine_row)

        # Pan Invert
        pan_inv_row = Adw.SwitchRow(title="Pan Yönünü Tersine Çevir (Natural Pan)")
        pan_inv_row.set_subtitle("Fareyi aşağı çekince sayfayı yukarı kaydırır")
        pan_inv_row.set_active(config.pan_invert)
        pan_inv_row.connect("notify::active", lambda r, _: (setattr(config, 'pan_invert', r.get_active()), config.save()))
        g.add(pan_inv_row)

        # Drag threshold
        tr = Adw.SpinRow.new_with_range(10, 200, 5)
        tr.set_title("Jest Sürükleme Eşiği (Drag Threshold)")
        tr.set_subtitle("Masaüstü değiştirme sürükleme piksel eşiği")
        tr.set_value(config.drag_threshold)
        tr.connect("notify::value", lambda r, _: (setattr(config, 'drag_threshold', int(r.get_value())), config.save()))
        g.add(tr)

        self._box.append(g)

    def _build_howto(self):
        g = Adw.PreferencesGroup(title="📖 Nasıl Çalışır?")
        items = [
            ("pan-up-symbolic", "Yan butona basılı tut + fareyi gezdir", "Excel ve web sayfalarında 2D Pan (Yatay + Dikey Kaydırma)"),
            ("go-next-symbolic", "Yan buton basılı + hızlı sağa/sola çek", "Masaüstü değiştirir"),
            ("zoom-in-symbolic", "Yan buton basılı + tekerlek", "Sayfayı Yakınlaştır / Uzaklaştır"),
            ("input-mouse-symbolic", "Yan butona sadece tıkla", "Geri/İleri navigasyon"),
            ("view-grid-symbolic", "Fareyi köşelere götür", "Hot corner eylemi tetikler"),
        ]
        for ic, t, s in items:
            row = Adw.ActionRow(title=t, subtitle=s)
            row.add_prefix(Gtk.Image.new_from_icon_name(ic))
            g.add(row)
        self._box.append(g)

    def _on_add(self, _):
        AddRemapDialog(self._do_add).present(self)

    def _do_add(self, b, t, a):
        config.add_remap(b, t, a)
        self._build_remaps()

    def _on_del(self, i):
        config.remove_remap(i)
        self._build_remaps()

    def _on_act_change(self, i, a):
        config.update_remap_action(i, a)

    def update_engine_status(self, running, msg):
        def _do():
            self._status_row.set_subtitle(msg)
            if running:
                self._status_dot.remove_css_class("status-inactive")
                self._status_dot.add_css_class("status-active")
                self._status_icon.set_from_icon_name("network-idle-symbolic")
                self._perm_banner.set_revealed(False)
            else:
                self._status_dot.remove_css_class("status-active")
                self._status_dot.add_css_class("status-inactive")
                self._status_icon.set_from_icon_name("network-offline-symbolic")
                self.check_perm_status()
        GLib.idle_add(_do)

    def update_device_info(self, name, buttons, caps):
        def _do():
            self._device_name_row.set_subtitle(name or "Bulunamadı")
            if buttons:
                btn_strs = [f"{b['name']}" for b in buttons]
                self._device_buttons_row.set_subtitle(" │ ".join(btn_strs))
            else:
                self._device_buttons_row.set_subtitle("Algılanamadı")
            if caps:
                feats = []
                if caps.get("wheel"): feats.append("🎡 Tekerlek")
                if caps.get("hwheel"): feats.append("↔️ Yatay Tekerlek")
                if caps.get("hires"): feats.append("✨ Hi-Res Scroll")
                self._device_caps_row.set_subtitle(" │ ".join(feats) if feats else "Standart")
            else:
                self._device_caps_row.set_subtitle("—")
        GLib.idle_add(_do)


class LinuxMouseFixApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.linuxmousefix.app", flags=Gio.ApplicationFlags.FLAGS_NONE)
        self._window = None
        self._engine = None

    def do_startup(self):
        Adw.Application.do_startup(self)
        for n, h in [("reset", self._on_reset), ("about", self._on_about)]:
            a = Gio.SimpleAction.new(n, None)
            a.connect("activate", h)
            self.add_action(a)
        self._load_css()

    def do_activate(self):
        if not self._window:
            self._window = LinuxMouseFixWindow(self)
            self._start_engine()
        self._window.present()

    def _load_css(self):
        css = b"""
        .remap-badge { border-radius: 10px; font-weight: 800; font-size: 14px; color: white; min-width: 36px; min-height: 36px; }
        .badge-btn-1 { background: #26a269; } .badge-btn-2 { background: #c64600; }
        .badge-btn-3 { background: #3584e4; } .badge-btn-4 { background: #e66100; }
        .badge-btn-5 { background: #9141ac; } .badge-btn-6 { background: #2ec27e; }
        .badge-btn-7 { background: #a51d2d; } .badge-btn-8 { background: #1a5fb4; }
        .badge-btn-9 { background: #613583; }
        .status-active  { color: #2ec27e; font-size: 22px; }
        .status-inactive { color: #e5a50a; font-size: 22px; }
        """
        p = Gtk.CssProvider()
        p.load_from_data(css)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), p, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def _start_engine(self):
        try:
            from engine import engine as eng
            eng.set_status_callback(lambda r, m: self._window.update_engine_status(r, m) if self._window else None)
            eng.set_device_info_callback(lambda n, b, c: self._window.update_device_info(n, b, c) if self._window else None)
            if not eng.is_alive():
                eng.start()
            self._engine = eng
        except Exception as e:
            if self._window:
                self._window.update_engine_status(False, f"Motor hatası: {e}")

    def _on_reset(self, *_):
        d = Adw.AlertDialog()
        d.set_heading("Varsayılana Sıfırla")
        d.set_body("Tüm ayarlar sıfırlanacak. Devam?")
        d.add_response("cancel", "İptal")
        d.add_response("reset", "Sıfırla")
        d.set_response_appearance("reset", Adw.ResponseAppearance.DESTRUCTIVE)
        d.set_default_response("cancel")
        d.set_close_response("cancel")
        def on_r(dl, resp):
            if resp == "reset":
                config.reset_to_defaults()
                self._window._enable_row.set_active(True)
                self._window._hc_switch.set_active(True)
                self._window._build_remaps()
        d.connect("response", on_r)
        d.present(self._window)

    def _on_about(self, *_):
        a = Adw.AboutDialog()
        a.set_application_name("Linux Mouse Fix")
        a.set_version("6.0.0")
        a.set_developer_name("LinuxMouseFix")
        a.set_application_icon("input-mouse-symbolic")
        a.set_comments("Mac Mouse Fix'ten ilham alınarak geliştirilmiş\nkapsamlı Ubuntu mouse gesture aracı.\n\n• 2D Pan / Sayfa Kaydırma (Excel/Tarayıcı)\n• Buton + kaydır → masaüstü değiştir\n• Buton + tekerlek → zoom\n• Hot corners")
        a.set_license_type(Gtk.License.MIT_X11)
        a.present(self._window)


def main():
    return LinuxMouseFixApp().run(sys.argv)

if __name__ == "__main__":
    main()
