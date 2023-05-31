#!/usr/bin/env python3

import os, sys, logging, subprocess
import gi
from cameractrls import CameraCtrls, find_by_text_id, get_devices, v4ldirs, find_idx
from cameractrls import version, ghurl

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gio, GLib, Pango, Gdk

logging.getLogger().setLevel(logging.INFO)

class CameraCtrlsWindow(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.devices = []
        
        self.fd = 0
        self.device = None
        self.camera = None

        self.grid = None
        self.frame = None
        self.device_dd = None

        self.init_window()
        self.refresh_devices()

    def init_window(self):
        css_provider = Gtk.CssProvider()
        css = '''
        #white-balance-temperature trough {
            background-image: linear-gradient(to right, 
                #89F3FF, #AFF7FF, #DDFCFF, #FFF2AA, #FFDD27, #FFC500, #FFB000, #FF8D00, #FF7A00
            );
        }
        #white-balance-temperature trough:disabled {
            background-blend-mode: color;
        }
        /* make page stackswitcher gtk3 size */
        stackswitcher button {
            padding-left: 10px;
            padding-right: 10px;
        }
        /* scale layout fix */
        scale trough {
            margin-top: 7px;
            margin-bottom: -7px;
        }
        '''
        # XXX: remove workaround when merged
        # https://gitlab.gnome.org/GNOME/pygobject/-/merge_requests/231/
        if (Gtk.get_major_version(), Gtk.get_minor_version()) >= (4, 9):
            css_provider.load_from_data(css, -1)
        else:
            css_provider.load_from_data(css.encode())

        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        hambuger_menu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        hambuger_menu.append(Gtk.Button(action_name='app.about', label='About', has_frame=False))

        hamburger_button = Gtk.MenuButton(
            popover=Gtk.Popover(position=Gtk.PositionType.BOTTOM, child=hambuger_menu),
            icon_name='open-menu-symbolic', has_frame=False,
        )

        self.open_cam_button = Gtk.Button(
            action_name='app.open_camera_window',
            action_target=GLib.Variant('s', ''),
            icon_name='camera-video-symbolic', has_frame=False,
        )

        refresh_button = Gtk.Button(icon_name='view-refresh-symbolic', has_frame=False)
        refresh_button.connect('clicked', lambda e: self.refresh_devices())

        headerbar = Gtk.HeaderBar(show_title_buttons=True)
        headerbar.pack_start(refresh_button)
        headerbar.pack_end(hamburger_button)
        headerbar.pack_end(self.open_cam_button)
        self.set_titlebar(headerbar)

        self.grid = Gtk.Grid()

        self.zero_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, halign=Gtk.Align.CENTER)
        self.zero_box.append(Gtk.Image(icon_name='camera-disabled-symbolic', icon_size=Gtk.IconSize.LARGE, pixel_size=96,
                                margin_top=30, margin_bottom=10, margin_start=80, margin_end=80))
        self.zero_box.append(Gtk.Label(label='<span size="17000" color="gray">0 camera found</span>', use_markup=True,
                                margin_top=10, margin_bottom=20))
        if 'SNAP' in os.environ:
            self.zero_box.append(Gtk.Label(label='Please permit access with', max_width_chars=30, wrap=True, margin_top=10))
            self.zero_box.append(Gtk.Label(label='snap connect cameractrls:camera', selectable=True, margin_bottom=10))

        self.device_dd = Gtk.DropDown(model=Gtk.StringList(), hexpand=True, show_arrow=False)
        # use the default factory as list_factory
        self.device_dd.set_list_factory(self.device_dd.get_factory())
        self.device_dd.get_first_child().set_has_frame(False)
        # then set the icon_factory as factory
        icon_factory = Gtk.SignalListItemFactory()
        icon_factory.connect('setup', lambda f, item: item.set_child(Gtk.Image(icon_name='camera-switch-symbolic')))
        self.device_dd.set_factory(icon_factory)

        self.device_dd.connect('notify::selected-item', lambda e, _: self.gui_open_device(self.device_dd.get_selected()))
        headerbar.pack_start(self.device_dd)

        self.grid.attach(self.zero_box, 0, 0, 1, 1)

        self._notify_timeout = None

        overlay = Gtk.Overlay()
        overlay.set_child(self.grid)

        # Notification overlay widget
        self._revealer = Gtk.Revealer(valign=Gtk.Align.END, halign=Gtk.Align.CENTER)
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        box.add_css_class('app-notification')
        self._notify_label = Gtk.Label(wrap=True, wrap_mode=Pango.WrapMode.CHAR, natural_wrap_mode=Gtk.NaturalWrapMode.NONE, halign=Gtk.Align.FILL)
        box.append(self._notify_label)
        button = Gtk.Button(icon_name='window-close-symbolic', halign=Gtk.Align.END, has_frame=False, receives_default=True)
        button.connect('clicked', lambda e: self._revealer.set_reveal_child(False))
        box.append(button)
        self._revealer.set_child(box)
        overlay.add_overlay(self._revealer)

        self.set_child(overlay)

    def refresh_devices(self):
        logging.info('refresh_devices')
        self.devices = get_devices(v4ldirs)

        if len(self.devices) == 0:
            self.close_device()
            self.init_gui_device()

        model = self.device_dd.get_model()
        model.splice(0, model.get_n_items(), [d.name for d in self.devices])

        if len(self.devices):
            idx = 0
            if self.device in self.devices:
                idx = self.devices.index(self.device)
            self.device_dd.set_selected(idx)

        if len(self.devices) == 0:
            self.zero_box.set_visible(True)
            self.device_dd.set_visible(False)
            self.open_cam_button.set_visible(False)
        else:
            self.zero_box.set_visible(False)
            self.device_dd.set_visible(True)
            self.open_cam_button.set_visible(True)

    def gui_open_device(self, id):
        # if the selection is empty
        if id == Gtk.INVALID_LIST_POSITION:
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
        logging.info(f'opening device: {device.path}')
        try:
            self.fd = os.open(device.path, os.O_RDWR, 0)
        except Exception as e:
            logging.error(f'os.open({device.path}, os.O_RDWR, 0) failed: {e}')

        self.camera = CameraCtrls(device.path, self.fd)
        self.device = device
        self.open_cam_button.set_action_target_value(GLib.Variant('s', self.device.path))

    def close_device(self):
        if self.fd:
            os.close(self.fd)
            self.fd = 0
            self.device = None
            self.camera = None

    def init_gui_device(self):
        if self.frame:
            self.grid.remove(self.frame)
            self.frame = None
            # forget old size
            self.set_default_size(-1, -1)

        if self.device == None:
            return

        self.frame = Gtk.Grid(hexpand=True, halign=Gtk.Align.FILL)
        self.grid.attach(self.frame, 0, 0, 1, 1)

        stack_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, vexpand=True, halign=Gtk.Align.FILL,
            margin_bottom=10, margin_top=10, margin_start=10, margin_end=10)
        stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT, transition_duration=500)
        stack_sw = Gtk.StackSwitcher(stack=stack, hexpand=True, halign=Gtk.Align.CENTER)
        stack_box.append(stack_sw)
        stack_box.append(stack)

        footer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin_top=10)
        stack_box.append(footer)

        self.frame.attach(stack_box, 0, 1, 1, 1)
        self.stack = stack

        for page in self.camera.get_ctrl_pages():
            page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            if page.target == 'main':
                stack.add_titled(page_box, page.title.lower(), page.title)
            elif page.target == 'footer':
                sep = Gtk.Separator(margin_bottom=10)
                footer.append(sep)
                footer.append(page_box)

            for cat in page.categories:
                if page.target != 'footer':
                    c_label = Gtk.Label(xalign=0, margin_bottom=10, margin_top=10)
                    c_label.set_markup(f'<b>{cat.title}</b>')
                    page_box.append(c_label)
                
                ctrls_frame = Gtk.Frame()
                page_box.append(ctrls_frame)

                ctrls_listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
                ctrls_listbox.set_header_func(lambda row, before: row.set_header(Gtk.Separator()) if before != None else None)
                ctrls_frame.set_child(ctrls_listbox)

                for c in cat.ctrls:
                    ctrl_row = Gtk.ListBoxRow()
                    ctrls_listbox.append(ctrl_row)

                    ctrl_box = Gtk.Box(margin_start=5, margin_end=5, height_request=45)
                    ctrl_row.set_child(ctrl_box)

                    label = Gtk.Label(label=c.name, xalign=0, margin_end=5)
                    tooltip_markup = f'<b>{c.text_id}</b>'
                    if c.kernel_id:
                        tooltip_markup += f'  <b>({c.kernel_id})</b>'
                    if c.tooltip:
                        tooltip_markup += f'\n\n{c.tooltip}'
                    label.set_tooltip_markup(tooltip_markup)
                    ctrl_box.append(label)

                    c.gui_ctrls = [label]

                    if c.type == 'integer':
                        adjustment = Gtk.Adjustment(lower=c.min, upper=c.max, value=c.value, step_increment=1)
                        adjustment.connect('value-changed', lambda a,c=c: self.update_ctrl(c, a.get_value()))
                        scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, hexpand=True, halign=Gtk.Align.END,
                            digits=0, has_origin=False, draw_value=True, value_pos=Gtk.PositionType.LEFT, adjustment=adjustment, width_request=264)
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
                        
                        refresh = Gtk.Button(icon_name='edit-undo-symbolic', valign=Gtk.Align.CENTER, halign=Gtk.Align.START, has_frame=False)
                        refresh.connect('clicked', lambda e, c=c, sc=scale: sc.get_adjustment().set_value(c.default))
                        ctrl_box.append(refresh)
                        ctrl_box.append(scale)
                        c.gui_ctrls += [scale, refresh]
                        c.gui_default_btn = refresh

                    elif c.type == 'boolean':
                        switch = Gtk.Switch(valign=Gtk.Align.CENTER, active=c.value, margin_end=5, hexpand=True, halign=Gtk.Align.END)
                        switch.connect('state-set', lambda a,b,c=c: self.update_ctrl(c, a.get_active()))
                        refresh = Gtk.Button(icon_name='edit-undo-symbolic', valign=Gtk.Align.CENTER, halign=Gtk.Align.START, has_frame=False)
                        if c.default != None:
                            refresh.connect('clicked', lambda e,switch=switch,c=c: switch.set_active(c.default))
                        ctrl_box.append(refresh)
                        ctrl_box.append(switch)
                        c.gui_ctrls += [switch, refresh]
                        c.gui_default_btn = refresh

                    elif c.type == 'button':
                        box = Gtk.Box(valign=Gtk.Align.CENTER, hexpand=True, halign=Gtk.Align.END)
                        box.add_css_class('linked')
                        ctrl_box.append(box)
                        for m in c.menu:
                            b = Gtk.Button(label=m.name, valign=Gtk.Align.CENTER)
                            b.connect('clicked', lambda e, c=c, m=m: self.update_ctrl(c, m.text_id))
                            box.append(b)
                            c.gui_ctrls += b
                        c.gui_default_btn = None

                    elif c.type == 'info':
                        label = Gtk.Label(label=c.value, selectable=True, justify=Gtk.Justification.RIGHT, hexpand=True,
                                            halign=Gtk.Align.END, wrap=True, wrap_mode=Pango.WrapMode.CHAR,
                                            max_width_chars=48, width_chars=32, xalign=1,
                                            natural_wrap_mode=Gtk.NaturalWrapMode.INHERIT)
                        ctrl_box.append(label)
                        c.gui_default_btn = None

                    elif c.type == 'menu':
                        if len(c.menu) < 4 and not c.menu_dd:
                            box = Gtk.Box(valign=Gtk.Align.CENTER, hexpand=True, halign=Gtk.Align.END)
                            box.add_css_class('linked')
                            rb = None
                            for m in c.menu:
                                rb = Gtk.ToggleButton(group=rb, label=m.name)
                                rb.set_active(m.text_id == c.value)
                                rb.connect('toggled', lambda b, c=c, m=m: self.update_ctrl(c, m.text_id) if b.get_active() else None)
                                box.append(rb)
                                m.gui_rb = rb

                            refresh = Gtk.Button(icon_name='edit-undo-symbolic', valign=Gtk.Align.CENTER, halign=Gtk.Align.START, has_frame=False)
                            if c.default != None:
                                refresh.connect('clicked', lambda e,c=c: find_by_text_id(c.menu, c.default).gui_rb.set_active(True))
                            ctrl_box.append(refresh)
                            ctrl_box.append(box)
                            c.gui_ctrls += [m.gui_rb for m in c.menu] + [refresh]
                            c.gui_default_btn = refresh
                        else:
                            wb_dd = Gtk.DropDown(model=Gtk.StringList(), valign=Gtk.Align.CENTER, hexpand=True, halign=Gtk.Align.END)
                            for m in c.menu:
                                wb_dd.get_model().append(m.name)
                            if c.value:
                                idx = find_idx(c.menu, lambda m: m.text_id == c.value)
                                if idx != None:
                                    wb_dd.set_selected(idx)
                                else:
                                    logging.warning(f'Control {c.text_id}: Can\'t find {c.value} in {[m.text_id for m in c.menu]}')
                            wb_dd.connect('notify::selected', lambda e,_,c=c: [
                                self.update_ctrl(c, c.menu[e.get_selected()].text_id),
                                # XXX: Workaround: GTK emits a signal or calls something later on the ComboBox widget,
                                # it can cause GTK assert warnings or a silent exit in some environments
                                #
                                # preserve_widget saves it to prevent to be destroyed by the GC
                                # it can be fixed properly with updating only the underlying model
                                # not to recreate everything in case the ctrl is a reopener
                                self.preserve_widget(e),
                                ])
                            refresh = Gtk.Button(icon_name='edit-undo-symbolic', valign=Gtk.Align.CENTER, halign=Gtk.Align.START, has_frame=False)
                            if c.default != None:
                                refresh.connect('clicked', lambda e,c=c,wb_dd=wb_dd: wb_dd.set_selected(find_idx(c.menu, lambda m: m.text_id == c.default)))
                            ctrl_box.append(refresh)
                            ctrl_box.append(wb_dd)
                            c.gui_ctrls += [wb_dd, refresh]
                            c.gui_default_btn = refresh

        self.update_ctrls_state()

    def close_notify(self):
        self._revealer.set_reveal_child(False)
        self._notify_timeout = None
        # False removes the timeout
        return False

    def notify(self, message, timeout=5):
        if self._notify_timeout is not None:
            GLib.Source.remove(self._notify_timeout)

        self._notify_label.set_text(message)
        self._revealer.set_reveal_child(True)

        if timeout > 0:
            self._notify_timeout = GLib.timeout_add_seconds(timeout, self.close_notify)

    def update_ctrl(self, ctrl, value):
        errs = []
        self.camera.setup_ctrls({ctrl.text_id: value}, errs)
        if errs:
            self.notify('\n'.join(errs))
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

        icon_theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        icon_theme.add_search_path(f'{sys.path[0]}/pkg')

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
        about.present()

    def on_quit(self, action, param):
        self.quit()

    def check_preview_open(self, p):
        # if process returned
        if p.poll() != None:
            (stdout, stderr) = p.communicate()
            errstr = str(stderr, 'utf-8')
            sys.stderr.write(errstr)
            if p.returncode != 0:
                self.window.notify(errstr.strip())
            # False removes the timeout
            return False
        return True

    def open_camera_window(self, action, device):
        win_width, win_height = self.window.get_default_size()
        logging.info(f'open cameraview.py for {device.get_string()} with max size {win_width}x{win_height}')
        p = subprocess.Popen([f'{sys.path[0]}/cameraview.py', '-d', device.get_string(), '-s', f'{win_width}x{win_height}'], stderr=subprocess.PIPE)
        self.child_processes.append(p)
        GLib.timeout_add(300, self.check_preview_open, p)

    def kill_child_processes(self):
        for proc in self.child_processes:
            proc.kill()


if __name__ == '__main__':
    app = CameraCtrlsApp()
    app.run()
    app.kill_child_processes()
