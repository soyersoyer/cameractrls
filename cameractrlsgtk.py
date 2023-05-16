#!/usr/bin/env python3

import os, sys, logging, subprocess
import gi
from cameractrls import CameraCtrls, find_by_text_id, get_devices, v4ldirs, find_idx
from cameractrls import version, ghurl

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gio, GLib, Pango, Gdk

class CameraCtrlsWindow(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, type_hint=Gdk.WindowTypeHint.DIALOG, **kwargs)
        self.devices = []
        
        self.fd = 0
        self.device = ''
        self.camera = None

        self.grid = None
        self.frame = None
        self.device_cb = None

        self.init_window()
        self.refresh_devices()

    def init_window(self):
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b'''
        #white-balance-temperature trough {
            background-image: linear-gradient(to right, 
                #89F3FF, #AFF7FF, #DDFCFF, #FFF2AA, #FFDD27, #FFC500, #FFB000, #FF8D00, #FF7A00
            );
        }
        #white-balance-temperature trough:disabled {
            background-blend-mode: color;
        }
        ''')

        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        hambuger_menu = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            margin=10, spacing=10,
            child=Gtk.ModelButton(action_name='app.about', label='About'),
        )
        hambuger_menu.show_all()

        hamburger_button = Gtk.MenuButton(
            popover=Gtk.Popover(position=Gtk.PositionType.BOTTOM, child=hambuger_menu),
            image=Gtk.Image.new_from_icon_name('open-menu-symbolic', Gtk.IconSize.MENU)
        )

        self.open_cam_button = Gtk.Button(
            action_name='app.open_camera_window',
            action_target=GLib.Variant('s', ''),
            image=Gtk.Image.new_from_icon_name('camera-video', Gtk.IconSize.MENU)
        )

        headerbar = Gtk.HeaderBar(title='Cameractrls', show_close_button=True)
        headerbar.pack_end(hamburger_button)
        headerbar.pack_end(self.open_cam_button)
        headerbar.show_all()
        self.set_titlebar(headerbar)

        self.grid = Gtk.Grid()

        self.zero_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, halign=Gtk.Align.CENTER)
        zero_label = Gtk.Label(label='0 camera found')
        zero_refresh = Gtk.Button(label='Refresh')
        zero_refresh.connect('clicked', lambda e: self.refresh_devices())
        self.zero_box.pack_start(zero_label, True, True, 10)
        self.zero_box.pack_start(zero_refresh, True, True, 5)
        self.zero_box.show_all()

        self.device_cb = Gtk.ComboBoxText()
        cellrenderer = self.device_cb.get_cells()[0]
        cellrenderer.set_property('ellipsize', Pango.EllipsizeMode.MIDDLE)
        cellrenderer.set_property('max-width-chars', 70)
        cellrenderer.set_property('width-chars', 70)
        self.device_cb.connect('changed', lambda e: self.gui_open_device(self.device_cb.get_active()))
        self.device_box = Gtk.Box(halign=Gtk.Align.FILL, hexpand=True, margin=10, margin_bottom=0)
        self.device_box.pack_start(self.device_cb, True, True, 0)
        self.device_box.show_all()

        self.grid.attach(self.zero_box, 0, 0, 1, 1)
        self.grid.show()
        self.add(self.grid)

    def refresh_devices(self):
        logging.info('refresh_devices')
        self.devices = get_devices(v4ldirs)
        
        if len(self.devices) == 0:
            self.close_device()
            self.init_gui_device()

        self.device_cb.remove_all()
        for device in self.devices:
            self.device_cb.append_text(device)
        self.device_cb.append_text('Refresh device list ...')

        if len(self.devices):
            if self.device not in self.devices:
                self.device_cb.set_active(0)
            else:
                idx = self.devices.index(self.device)
                self.device_cb.set_active(idx)

        if len(self.devices) == 0:
            if self.device_box.get_parent() != None:
                self.grid.remove(self.device_box)
                self.grid.attach(self.zero_box, 0, 0, 1, 1)
            self.open_cam_button.hide()
        elif len(self.devices) != 0:
            if self.zero_box.get_parent() != None:
                self.grid.remove(self.zero_box)
                self.grid.attach(self.device_box, 0, 0, 1, 1)
            self.open_cam_button.show()

    def gui_open_device(self, id):
        # if the selection is empty (after remove_all)
        if id == -1:
            return
        # after the last device there is the refresh
        if id == len(self.devices):
            self.refresh_devices()
            return

        self.close_device()
        self.open_device(self.devices[id])
        self.init_gui_device()

    def reopen_device(self):
        opened_page = self.stack.get_visible_child_name()
        device = self.device
        self.close_device()
        self.open_device(device)
        self.init_gui_device()
        self.stack.set_visible_child_full(opened_page, Gtk.StackTransitionType.NONE)

    def open_device(self, device):
        logging.info(f'opening device: {device}')
        try:
            self.fd = os.open(device, os.O_RDWR, 0)
        except Exception as e:
            logging.error(f'os.open({device}, os.O_RDWR, 0) failed: {e}')

        self.camera = CameraCtrls(device, self.fd)
        self.device = device
        self.open_cam_button.set_action_target_value(GLib.Variant('s', self.device))

    def close_device(self):
        if self.fd:
            os.close(self.fd)
            self.fd = 0
            self.device = ''
            self.camera = None

    def init_gui_device(self):
        if self.frame:
            self.frame.destroy()
            # forget old size
            self.resize(1,1)

        if self.device == '':
            return

        self.frame = Gtk.Grid(hexpand=True, halign=Gtk.Align.FILL)
        self.grid.attach(self.frame, 0, 1, 1, 1)

        stack_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin=10, vexpand=True, halign=Gtk.Align.FILL)
        stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT, transition_duration=500)
        stack_sw = Gtk.StackSwitcher(stack=stack, hexpand=True, halign=Gtk.Align.CENTER)
        stack_box.pack_start(stack_sw, False, False, 0)
        stack_box.pack_start(stack, False, False, 0)

        footer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin_top=10)
        stack_box.pack_start(footer, False, False, 0)

        self.frame.attach(stack_box, 0, 1, 1, 1)
        self.stack = stack

        for page in self.camera.get_ctrl_pages():
            page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            if page.target == 'main':
                stack.add_titled(page_box, page.title.lower(), page.title)
            elif page.target == 'footer':
                sep = Gtk.Separator(margin_bottom=10)
                footer.add(sep)
                footer.add(page_box)

            for cat in page.categories:
                if page.target != 'footer':
                    c_label = Gtk.Label(xalign=0, margin_bottom=10, margin_top=10)
                    c_label.set_markup(f'<b>{cat.title}</b>')
                    page_box.pack_start(c_label, False, False, 0)
                
                ctrls_frame = Gtk.Frame()
                page_box.pack_start(ctrls_frame, False, False, 0)

                ctrls_listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
                ctrls_listbox.set_header_func(lambda row, before: row.set_header(Gtk.Separator()) if before != None else None)
                ctrls_frame.add(ctrls_listbox)

                for c in cat.ctrls:
                    ctrl_row = Gtk.ListBoxRow()
                    ctrls_listbox.add(ctrl_row)

                    ctrl_box = Gtk.Box(margin_left=5, margin_right=5, height_request=45)
                    ctrl_row.add(ctrl_box)

                    label = Gtk.Label(label=c.name, xalign=0, margin_right=5)
                    tooltip_markup = f'<b>{c.text_id}</b>'
                    if c.kernel_id:
                        tooltip_markup += f'  <b>({c.kernel_id})</b>'
                    if c.tooltip:
                        tooltip_markup += f'\n\n{c.tooltip}'
                    label.set_tooltip_markup(tooltip_markup)
                    ctrl_box.pack_start(label, False, False, 0)

                    c.gui_ctrls = [label]

                    if c.type == 'integer':
                        adjustment = Gtk.Adjustment(lower=c.min, upper=c.max, value=c.value, step_increment=1)
                        adjustment.connect('value-changed', lambda a,c=c: self.update_ctrl(c, a.get_value()))
                        scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL,
                            digits=0, has_origin=False, value_pos=Gtk.PositionType.LEFT, adjustment=adjustment, width_request=264)
                        if c.zeroer:
                            scale.connect('button-release-event', lambda sc, e: sc.set_value(0))
                            scale.connect('key-release-event', lambda sc, e: sc.set_value(0))
                        if c.step and c.step != 1:
                            adjustment_step = Gtk.Adjustment(lower=c.min, upper=c.max, value=c.value, step_increment=c.step)
                            adjustment_step.connect('value-changed', lambda a,c=c,a1=adjustment: [a.set_value(a.get_value() - a.get_value() % c.step),a1.set_value(a.get_value())])
                            scale.set_adjustment(adjustment_step)
                        if c.wbtemperature:
                            scale.set_name('white-balance-temperature')

                        if c.default != None:
                            scale.add_mark(value=c.default, position=Gtk.PositionType.BOTTOM, markup=None)
                        
                        refresh = Gtk.Button(image=Gtk.Image.new_from_icon_name('edit-undo', Gtk.IconSize.BUTTON), valign=Gtk.Align.CENTER, halign=Gtk.Align.START, relief=Gtk.ReliefStyle.NONE)
                        refresh.connect('clicked', lambda e, c=c, sc=scale: sc.get_adjustment().set_value(c.default))
                        ctrl_box.pack_start(refresh, False, False, 0)
                        ctrl_box.pack_end(scale, False, False, 0)
                        c.gui_ctrls += [scale, refresh]
                        c.gui_default_btn = refresh

                    elif c.type == 'boolean':
                        switch = Gtk.Switch(valign=Gtk.Align.CENTER, active=c.value, margin_right=5)
                        switch.connect('state-set', lambda a,b,c=c: self.update_ctrl(c, a.get_active()))
                        refresh = Gtk.Button(image=Gtk.Image.new_from_icon_name('edit-undo', Gtk.IconSize.BUTTON), valign=Gtk.Align.CENTER, halign=Gtk.Align.START, relief=Gtk.ReliefStyle.NONE)
                        if c.default != None:
                            refresh.connect('clicked', lambda e,switch=switch,c=c: switch.set_active(c.default))
                        ctrl_box.pack_start(refresh, False, False, 0)
                        ctrl_box.pack_end(switch, False, False, 0)
                        c.gui_ctrls += [switch, refresh]
                        c.gui_default_btn = refresh

                    elif c.type == 'button':
                        box = Gtk.ButtonBox(valign=Gtk.Align.CENTER)
                        box.set_layout(Gtk.ButtonBoxStyle.EXPAND)
                        ctrl_box.pack_end(box, False, False, 0)
                        for m in c.menu:
                            b = Gtk.Button(label=m.name, valign=Gtk.Align.CENTER)
                            b.connect('clicked', lambda e, c=c, m=m: self.update_ctrl(c, m.text_id))
                            box.add(b)
                            c.gui_ctrls += b
                        c.gui_default_btn = None

                    elif c.type == 'menu':
                        if len(c.menu) < 4 and not c.menu_dd:
                            box = Gtk.ButtonBox(valign=Gtk.Align.CENTER)
                            box.set_layout(Gtk.ButtonBoxStyle.EXPAND)
                            box.set_homogeneous(False)
                            rb = None
                            for m in c.menu:
                                rb = Gtk.RadioButton.new_with_label_from_widget(radio_group_member=rb, label=m.name)
                                rb.set_mode(False)
                                rb.set_active(m.text_id == c.value)
                                rb.connect('toggled', lambda b, c=c, m=m: self.update_ctrl(c, m.text_id) if b.get_active() else None)
                                box.add(rb)
                                m.gui_rb = rb
                            if c.value == None:
                                rb = Gtk.RadioButton.new_with_label_from_widget(radio_group_member=rb, label='Undefined')
                                rb.set_mode(False)
                                rb.set_active(True)
                                rb.set_no_show_all(True)
                                box.add(rb)

                            refresh = Gtk.Button(image=Gtk.Image.new_from_icon_name('edit-undo', Gtk.IconSize.BUTTON), valign=Gtk.Align.CENTER, halign=Gtk.Align.START, relief=Gtk.ReliefStyle.NONE)
                            if c.default != None:
                                refresh.connect('clicked', lambda e,c=c: find_by_text_id(c.menu, c.default).gui_rb.set_active(True))
                            ctrl_box.pack_start(refresh, False, False, 0)
                            ctrl_box.pack_end(box, False, False, 0)
                            c.gui_ctrls += [m.gui_rb for m in c.menu] + [refresh]
                            c.gui_default_btn = refresh
                        else:
                            wb_cb = Gtk.ComboBoxText(valign=Gtk.Align.CENTER)
                            for m in c.menu:
                                wb_cb.append_text(m.name)
                            if c.value:
                                idx = find_idx(c.menu, lambda m: m.text_id == c.value)
                                if idx != None:
                                    wb_cb.set_active(idx)
                                else:
                                    logging.warning(f'Control {c.text_id}: Can\'t find {c.value} in {[m.text_id for m in c.menu]}')
                            wb_cb.connect('changed', lambda e,c=c: [
                                self.update_ctrl(c, c.menu[e.get_active()].text_id),
                                # XXX: Workaround: GTK emits a signal or calls something later on the ComboBox widget,
                                # it can cause GTK assert warnings or a silent exit in some environments
                                #
                                # preserve_widget saves it to prevent to be destroyed by the GC
                                # it can be fixed properly with updating only the underlying model
                                # not to recreate everything in case the ctrl is a reopener
                                self.preserve_widget(e),
                                ])
                            refresh = Gtk.Button(image=Gtk.Image.new_from_icon_name('edit-undo', Gtk.IconSize.BUTTON), valign=Gtk.Align.CENTER, halign=Gtk.Align.START, relief=Gtk.ReliefStyle.NONE)
                            if c.default != None:
                                refresh.connect('clicked', lambda e,c=c,wb_cb=wb_cb: wb_cb.set_active(find_idx(c.menu, lambda m: m.text_id == c.default)))
                            ctrl_box.pack_start(refresh, False, False, 0)
                            ctrl_box.pack_end(wb_cb, False, False, 0)
                            c.gui_ctrls += [wb_cb, refresh]
                            c.gui_default_btn = refresh

        self.update_ctrls_state()
        self.grid.show_all()

    def update_ctrl(self, ctrl, value):
        self.camera.setup_ctrls({ctrl.text_id: value}),
        if ctrl.updater:
            self.camera.update_ctrls()
        self.update_ctrls_state()
        if ctrl.reopener:
            self.reopen_device()

    def update_ctrls_state(self):
        for c in self.camera.get_ctrls():
            for gui_ctrl in c.gui_ctrls:
                gui_ctrl.set_sensitive(not c.inactive)
            if c.gui_default_btn != None:
                c.gui_default_btn.set_opacity(0 if c.default == None or c.default == c.value else 1)
                c.gui_default_btn.set_can_focus(0 if c.default == None or c.default == c.value else 1)

    def preserve_widget(self, widget):
        self.preserved_widget = widget

class CameraCtrlsApp(Gtk.Application):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, application_id='hu.irl.cameractrls', **kwargs)

        self.window = None
        self.child_processes = []

    def do_startup(self):
        Gtk.Application.do_startup(self)

        action = Gio.SimpleAction.new('about', None)
        action.connect('activate', self.on_about)
        self.add_action(action)

        action = Gio.SimpleAction.new('open_camera_window', GLib.VariantType('s'))
        action.connect('activate', self.open_camera_window)
        self.add_action(action)

        action = Gio.SimpleAction.new('quit', None)
        action.connect('activate', self.on_quit)
        self.add_action(action)

        self.set_accels_for_action('app.quit',["<Primary>Q"])

    def do_activate(self):
        self.window = CameraCtrlsWindow(application=self, title='Cameractrls')
        self.window.present()

    def on_about(self, action, param):
        about = Gtk.AboutDialog(transient_for=self.window, modal=self.window)
        about.set_program_name('Cameractrls')
        about.set_authors(['Gergo Koteles <soyer@irl.hu>'])
        about.set_artists(['Jorge Toledo https://lacajita.es'])
        about.set_copyright('Copyright © 2022 - 2023 Gergo Koteles')
        about.set_license_type(Gtk.License.MIT_X11)
        about.set_logo_icon_name('hu.irl.cameractrls')
        about.set_website(ghurl)
        about.set_website_label('GitHub')
        about.set_version(version)
        about.connect('response', lambda d, r: d.destroy())
        about.present()

    def on_quit(self, action, param):
        self.quit()

    def open_camera_window(self, action, device):
        p = subprocess.Popen([f'{sys.path[0]}/cameraview.py', '-d', device.get_string()])
        self.child_processes.append(p)

    def kill_child_processes(self):
        for proc in self.child_processes:
            proc.kill()


if __name__ == '__main__':
    app = CameraCtrlsApp()
    app.run()
    app.kill_child_processes()
