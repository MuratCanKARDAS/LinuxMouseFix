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
        self.set_default_size(660, 780)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Permission Banner at very top
        self._perm_banner = Adw.Banner()
        self._perm_banner.set_title("⚠️ Mouse erişim izinleri eksik.")
        self._perm_banner.set_button_label("İzinleri Yapılandır")
        self._perm_banner.connect("button-clicked", self._on_fix_permissions)
        self._perm_banner.set_revealed(False)
        main_box.append(self._perm_banner)

        # ToolbarView with ViewSwitcher in header
        tv = Adw.ToolbarView()
        hdr = Adw.HeaderBar()
        self._stack = Adw.ViewStack()
        switcher = Adw.ViewSwitcher(stack=self._stack, policy=Adw.ViewSwitcherPolicy.WIDE)
        hdr.set_title_widget(switcher)
        menu = Gio.Menu()
        menu.append("Varsayılana Sıfırla", "app.reset")
        menu.append("Hakkında", "app.about")
        hdr.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu))
        tv.add_top_bar(hdr)

        # Bottom switcher bar for narrow windows
        bottom_bar = Adw.ViewSwitcherBar(stack=self._stack)
        tv.add_bottom_bar(bottom_bar)

        # --- Tab 1: Overview ---
        page1 = self._build_overview_page()
        self._stack.add_titled_with_icon(page1, "overview", "Genel", "go-home-symbolic")

        # --- Tab 2: Remaps ---
        page2 = self._build_remaps_page()
        self._stack.add_titled_with_icon(page2, "remaps", "Atamalar", "input-mouse-symbolic")

        # --- Tab 3: Settings ---
        page3 = self._build_settings_page()
        self._stack.add_titled_with_icon(page3, "settings", "Ayarlar", "emblem-system-symbolic")

        # --- Tab 4: Hot Corners ---
        page4 = self._build_hot_corners_page()
        self._stack.add_titled_with_icon(page4, "hotcorners", "Köşeler", "view-grid-symbolic")

        tv.set_content(self._stack)
        main_box.append(tv)
        self.set_content(main_box)
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

    # ── Helper: scrollable page shell ──
    def _make_page(self):
        scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        clamp = Adw.Clamp(maximum_size=660)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        box.set_margin_top(20); box.set_margin_bottom(40)
        box.set_margin_start(16); box.set_margin_end(16)
        clamp.set_child(box)
        scroll.set_child(clamp)
        return scroll, box

    # ═══════════════ TAB 1: OVERVIEW ═══════════════
    def _build_overview_page(self):
        page, box = self._make_page()

        # Status card
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
        box.append(g)

        # Device info
        dg = Adw.PreferencesGroup(title="Algılanan Cihaz")
        self._device_name_row = Adw.ActionRow(title="Cihaz", subtitle="Algılanıyor...")
        self._device_name_row.add_prefix(Gtk.Image.new_from_icon_name("input-mouse-symbolic"))
        dg.add(self._device_name_row)
        self._device_buttons_row = Adw.ActionRow(title="Butonlar", subtitle="—")
        self._device_buttons_row.add_prefix(Gtk.Image.new_from_icon_name("preferences-desktop-peripherals-symbolic"))
        dg.add(self._device_buttons_row)
        self._device_caps_row = Adw.ActionRow(title="Özellikler", subtitle="—")
        self._device_caps_row.add_prefix(Gtk.Image.new_from_icon_name("dialog-information-symbolic"))
        dg.add(self._device_caps_row)
        box.append(dg)

        # How-to guide
        hg = Adw.PreferencesGroup(title="Nasıl Çalışır?")
        for ic, t, s in [
            ("pan-up-symbolic", "Yan buton basılı + fareyi gezdir", "2D Pan (Yatay + Dikey Kaydırma)"),
            ("go-next-symbolic", "Yan buton basılı + sağa/sola çek", "Masaüstü değiştirir"),
            ("zoom-in-symbolic", "Yan buton basılı + tekerlek", "Yakınlaştır / Uzaklaştır"),
            ("input-mouse-symbolic", "Yan butona sadece tıkla", "Geri/İleri navigasyon"),
            ("view-grid-symbolic", "Fareyi köşelere götür", "Hot corner eylemi"),
        ]:
            row = Adw.ActionRow(title=t, subtitle=s)
            row.add_prefix(Gtk.Image.new_from_icon_name(ic))
            hg.add(row)
        box.append(hg)
        return page

    # ═══════════════ TAB 2: REMAPS ═══════════════
    def _build_remaps_page(self):
        page, box = self._make_page()
        self._remaps_container = box
        self._build_remaps()
        return page

    def _build_remaps(self):
        child = self._remaps_container.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self._remaps_container.remove(child)
            child = nxt
        g = Adw.PreferencesGroup(title="Buton Atamaları", description="Buton + hareket/tekerlek → eylem")
        ab = Gtk.Button(icon_name="list-add-symbolic")
        ab.add_css_class("flat"); ab.set_tooltip_text("Yeni atama ekle")
        ab.set_valign(Gtk.Align.CENTER)
        ab.connect("clicked", self._on_add)
        g.set_header_suffix(ab)
        if not config.remaps:
            g.add(Adw.ActionRow(title="Henüz atama yok", subtitle="Sağ üstteki + ile yeni atama ekleyin"))
        else:
            for i, r in enumerate(config.remaps):
                g.add(RemapRow(i, r, self._on_del, self._on_act_change))
        self._remaps_container.append(g)

    # ═══════════════ TAB 3: SETTINGS ═══════════════
    def _build_settings_page(self):
        page, box = self._make_page()

        g1 = Adw.PreferencesGroup(title="2D Pan Kaydırma")
        pan_sens = Adw.SpinRow.new_with_range(5, 100, 5)
        pan_sens.set_title("Hassasiyet")
        pan_sens.set_subtitle("Yüksek = Yavaş/Hassas, Düşük = Hızlı")
        pan_sens.set_value(config.pan_sensitivity)
        pan_sens.connect("notify::value", lambda r, _: (setattr(config, 'pan_sensitivity', int(r.get_value())), config.save()))
        g1.add(pan_sens)

        pan_ine = Adw.SpinRow.new_with_range(0, 100, 5)
        pan_ine.set_title("Momentum Süzülme")
        pan_ine.set_subtitle("0 = Anında Dur, 50 = Normal, 100 = Uzun Süzülme")
        pan_ine.set_value(config.pan_inertia)
        pan_ine.connect("notify::value", lambda r, _: (setattr(config, 'pan_inertia', int(r.get_value())), config.save()))
        g1.add(pan_ine)

        pan_inv = Adw.SwitchRow(title="Doğal Yön (Natural Pan)")
        pan_inv.set_subtitle("Fareyi aşağı çekince sayfayı yukarı kaydırır")
        pan_inv.set_active(config.pan_invert)
        pan_inv.connect("notify::active", lambda r, _: (setattr(config, 'pan_invert', r.get_active()), config.save()))
        g1.add(pan_inv)
        box.append(g1)

        g2 = Adw.PreferencesGroup(title="Jest ve Sürükleme")
        drag_tr = Adw.SpinRow.new_with_range(10, 200, 5)
        drag_tr.set_title("Sürükleme Eşiği")
        drag_tr.set_subtitle("Masaüstü değiştirme piksel eşiği")
        drag_tr.set_value(config.drag_threshold)
        drag_tr.connect("notify::value", lambda r, _: (setattr(config, 'drag_threshold', int(r.get_value())), config.save()))
        g2.add(drag_tr)
        box.append(g2)
        return page

    # ═══════════════ TAB 4: HOT CORNERS ═══════════════
    def _build_hot_corners_page(self):
        page, box = self._make_page()
        g = Adw.PreferencesGroup(title="Sıcak Köşeler", description="Fareyi köşeye götürünce eylem tetiklenir")
        self._hc_switch = Adw.SwitchRow(title="Hot Corner Aktif")
        self._hc_switch.set_active(config.hot_corner_enabled)
        self._hc_switch.connect("notify::active", lambda r, _: (setattr(config, 'hot_corner_enabled', r.get_active()), config.save()))
        g.add(self._hc_switch)
        hc_keys = list(HOT_CORNER_ACTIONS.keys())
        for cid, clabel in [("top_left","↖ Sol Üst"),("top_right","↗ Sağ Üst"),("bottom_left","↙ Sol Alt"),("bottom_right","↘ Sağ Alt")]:
            model = Gtk.StringList()
            for k in hc_keys:
                model.append(HOT_CORNER_ACTIONS[k])
            row = Adw.ComboRow(title=clabel, model=model)
            cur = config.get_hot_corner_action(cid)
            try: row.set_selected(hc_keys.index(cur))
            except ValueError: pass
            row.connect("notify::selected", self._make_hc_handler(cid, hc_keys))
            g.add(row)
        box.append(g)

        g2 = Adw.PreferencesGroup(title="Köşe Ayarları")
        delay = Adw.SpinRow.new_with_range(0, 1000, 50)
        delay.set_title("Gecikme (ms)")
        delay.set_value(config.hot_corner_delay_ms)
        delay.connect("notify::value", lambda r, _: (setattr(config, 'hot_corner_delay_ms', int(r.get_value())), config.save()))
        g2.add(delay)
        sz = Adw.SpinRow.new_with_range(1, 30, 1)
        sz.set_title("Köşe Boyutu (px)")
        sz.set_value(config.hot_corner_size)
        sz.connect("notify::value", lambda r, _: (setattr(config, 'hot_corner_size', int(r.get_value())), config.save()))
        g2.add(sz)
        box.append(g2)
        return page

    def _make_hc_handler(self, corner_id, keys):
        def handler(row, _):
            idx = row.get_selected()
            if 0 <= idx < len(keys):
                config.set_hot_corner(corner_id, keys[idx])
        return handler

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
        .remap-badge {
            border-radius: 12px; font-weight: 800; font-size: 13px;
            color: white; min-width: 34px; min-height: 34px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.18);
        }
        .badge-btn-1 { background: linear-gradient(135deg, #2ec27e, #26a269); }
        .badge-btn-2 { background: linear-gradient(135deg, #e66100, #c64600); }
        .badge-btn-3 { background: linear-gradient(135deg, #62a0ea, #3584e4); }
        .badge-btn-4 { background: linear-gradient(135deg, #ff7800, #e66100); }
        .badge-btn-5 { background: linear-gradient(135deg, #c061cb, #9141ac); }
        .badge-btn-6 { background: linear-gradient(135deg, #57e389, #2ec27e); }
        .badge-btn-7 { background: linear-gradient(135deg, #ed333b, #a51d2d); }
        .badge-btn-8 { background: linear-gradient(135deg, #3584e4, #1a5fb4); }
        .badge-btn-9 { background: linear-gradient(135deg, #9141ac, #613583); }
        .status-active  { color: #2ec27e; font-size: 24px; text-shadow: 0 0 8px rgba(46,194,126,0.5); }
        .status-inactive { color: #e5a50a; font-size: 24px; }
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
        a.set_version("7.0.0")
        a.set_developer_name("Murat Can KARDAS")
        a.set_application_icon("input-mouse-symbolic")
        a.set_comments("Mac Mouse Fix'ten ilham alınarak geliştirilmiş\nLinux mouse gesture ve 2D pan aracı.\n\n• Momentum destekli 2D Pan kaydırma\n• Buton + sürükleme jestleri\n• Sıcak köşe eylemleri\n• Tam özelleştirme")
        a.set_license_type(Gtk.License.MIT_X11)
        a.present(self._window)


def main():
    return LinuxMouseFixApp().run(sys.argv)

if __name__ == "__main__":
    main()
