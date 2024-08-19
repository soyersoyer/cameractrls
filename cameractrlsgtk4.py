#!/usr/bin/env python3

import os, sys, logging, subprocess
import gi
from cameractrls import CameraCtrls, PTZHWControllers, find_by_text_id, get_devices, v4ldirs, find_idx
from cameractrls import version, ghurl

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gio, GLib, Pango, Gdk

#logging.getLogger().setLevel(logging.INFO)

class CameraCtrlsWindow(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.devices = []
        
        self.fd = 0
        self.device = None
        self.camera = None
        self.listener = None
        self.ptz_controllers = None

        self.grid = None
        self.frame = None
        self.device_dd = None

        self.zoom_absolute_sc = None
        self.pan_speed_sc = None
        self.tilt_speed_sc = None
        self.pan_absolute_sc = None
        self.tilt_absolute_sc = None

        self.init_window()
        self.refresh_devices()

    def init_window(self):
        css_provider = Gtk.CssProvider()
        css = '''
        .white-balance-temperature trough {
            background-image: linear-gradient(to right, 
                #89F3FF, #AFF7FF, #DDFCFF, #FFF2AA, #FFDD27, #FFC500, #FFB000, #FF8D00, #FF7A00
            );
        }
        .white-balance-temperature trough:disabled {
            background-blend-mode: color;
        }
        .dark-to-light trough {
            background-image: linear-gradient(to right, 
                #888888, #dddddd
            );
        }
        .dark-to-light trough:disabled {
            background-blend-mode: color;
        }
        /* make page stackswitcher gtk3 size */
        stackswitcher button {
            padding-left: 10px;
            padding-right: 10px;
        }
        '''

        gtk_version = (Gtk.get_major_version(), Gtk.get_minor_version(), Gtk.get_micro_version())

        if gtk_version >= (4, 14, 2):
            css += '''
            /* scale layout fix */
            scale {
                padding: 8px;
            }
            '''
        else:
            css += '''
            /* scale layout fix */
            scale trough {
                margin-top: 7px;
                margin-bottom: -7px;
            }
            '''

        if gtk_version >= (4, 12, 0):
            css_provider.load_from_string(css)
        # XXX: remove workaround when merged and pygobject 3.46 is widespread
        # https://gitlab.gnome.org/GNOME/pygobject/-/merge_requests/231/
        elif gtk_version >= (4, 9, 0):
            css_provider.load_from_data(css, -1)
        else:
            css_provider.load_from_data(css.encode())

        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        try:
            self.desktop_portal = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION, Gio.DBusProxyFlags.NONE, None,
                'org.freedesktop.portal.Desktop', '/org/freedesktop/portal/desktop',
                'org.freedesktop.portal.Settings', None)
            prefer_dark = self.desktop_portal.Read('(ss)', 'org.freedesktop.appearance', 'color-scheme') == 1
            self.get_settings().set_property('gtk-application-prefer-dark-theme', prefer_dark)
            self.desktop_portal.connect('g-signal', lambda p, sender, signal, params:
                signal == 'SettingChanged' and
                params[0] == 'org.freedesktop.appearance' and
                params[1] == 'color-scheme' and
                self.get_settings().set_property('gtk-application-prefer-dark-theme', params[2] == 1)
            )
        except Exception as e:
            logging.warning(f'desktop_portal failed: {e}')

        about_button = Gtk.Button(
            action_name='app.about',
            icon_name='open-menu-symbolic',
            has_frame=False,
            tooltip_text='About',
        )

        self.open_cam_button = Gtk.Button(
            action_name='app.open_camera_window',
            action_target=GLib.Variant('s', ''),
            icon_name='camera-video-symbolic', has_frame=False,
            tooltip_text='Show preview window',
        )

        self.ptz_model = Gtk.StringList()
        self.ptz_lb = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.ptz_lb.bind_model(self.ptz_model, lambda name: Gtk.ToggleButton(label=name.get_string()))

        self.ptz_sw = Gtk.MenuButton(
            popover=Gtk.Popover(position=Gtk.PositionType.BOTTOM, child=self.ptz_lb),
            icon_name='input-gaming-symbolic',
            has_frame=False,
            tooltip_text='PTZ hardware controls',
        )

        refresh_button = Gtk.Button(icon_name='view-refresh-symbolic', has_frame=False, tooltip_text='Refresh')
        refresh_button.connect('clicked', lambda e: self.refresh_devices())

        headerbar = Gtk.HeaderBar(show_title_buttons=True)
        headerbar.pack_start(refresh_button)
        headerbar.pack_end(about_button)
        headerbar.pack_end(self.open_cam_button)
        headerbar.pack_end(self.ptz_sw)
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

        self.device_dd = Gtk.DropDown(
            model=Gtk.StringList(), hexpand=True, halign=Gtk.Align.START, show_arrow=False,
            tooltip_text='Select other camera',
        )
        # use the default factory as list_factory
        self.device_dd.set_list_factory(self.device_dd.get_factory())
        self.device_dd.get_first_child().set_has_frame(False)
        # then set the icon_factory as factory
        icon_factory = Gtk.SignalListItemFactory()
        icon_factory.connect('setup', lambda f, item: item.set_child(Gtk.Image(icon_name='view-more-symbolic')))
        self.device_dd.set_factory(icon_factory)

        self.device_dd.connect('notify::selected-item', lambda e, _: self.gui_open_device(self.device_dd.get_selected()))
        headerbar.pack_start(self.device_dd)

        self.grid.attach(self.zero_box, 0, 0, 1, 1)

        self._notify_timeout = None

        overlay = Gtk.Overlay()
        overlay.set_child(self.grid)

        # Notification overlay widget
        self._revealer = Gtk.Revealer(valign=Gtk.Align.END, halign=Gtk.Align.CENTER)
        self._notify_label = Gtk.Label(wrap=True, wrap_mode=Pango.WrapMode.CHAR, natural_wrap_mode=Gtk.NaturalWrapMode.NONE, halign=Gtk.Align.FILL)
        self._notify_label.add_css_class('app-notification')
        self._revealer.set_child(self._notify_label)
        overlay.add_overlay(self._revealer)

        self.set_child(overlay)

        self.connect('close-request', lambda w: self.close_device())

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
        logging.info('gui_open_device')
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
        self.listener = self.camera.subscribe_events(
            lambda c: GLib.idle_add(self.update_ctrl_value, c),
            lambda errs: GLib.idle_add(self.notify, '\n'.join(errs)),
        )
        self.device = device
        self.ptz_controllers = PTZHWControllers(self.device.path,
            lambda check, p, i: GLib.timeout_add(300, check, p, i),
            lambda err: self.notify(err),
            lambda i: self.ptz_lb.get_row_at_index(i).get_child().set_active(False),
        )
        self.ptz_model.splice(0, self.ptz_model.get_n_items(), self.ptz_controllers.get_names())
        for i in range(self.ptz_model.get_n_items()):
            row = self.ptz_lb.get_row_at_index(i)
            row.set_activatable(False)
            row.set_focusable(False)
            row.get_child().connect('toggled', lambda c, i=i: self.ptz_controllers.set_active(i, c.get_active()))
        self.ptz_sw.set_visible(self.camera.has_ptz())
        self.ptz_sw.set_sensitive(self.ptz_model.get_n_items() != 0)
        self.open_cam_button.set_action_target_value(GLib.Variant('s', self.device.path))

    def close_device(self):
        if self.fd:
            logging.info('close_device')    
            self.device = None
            self.camera = None
            self.listener.stop()
            self.listener = None
            self.ptz_controllers.terminate_all()
            self.ptz_controllers = None
            os.close(self.fd)
            self.fd = 0

    def init_gui_device(self):
        if self.frame:
            self.grid.remove(self.frame)
            self.frame = None

        if self.device is None:
            return

        self.frame = Gtk.Grid(hexpand=True, halign=Gtk.Align.FILL)
        self.grid.attach(self.frame, 0, 0, 1, 1)

        stack_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, vexpand=True, halign=Gtk.Align.FILL,
            margin_bottom=10, margin_top=10, margin_start=10, margin_end=10)
        stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT, transition_duration=500)
        stack_sw = Gtk.StackSwitcher(stack=stack, hexpand=True, halign=Gtk.Align.CENTER)
        stack_box.append(stack_sw)
        scrolledwindow = Gtk.ScrolledWindow(child=stack, propagate_natural_height=True, hscrollbar_policy=Gtk.PolicyType.NEVER, vscrollbar_policy=Gtk.PolicyType.AUTOMATIC)
        stack_box.append(scrolledwindow)

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
                ctrls_listbox.set_header_func(lambda row, before: row.set_header(Gtk.Separator()) if before is not None else None)
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
                    c.gui_value_set = None

                    if c.type == 'integer':
                        adjustment = Gtk.Adjustment(lower=c.min, upper=c.max, value=c.value, step_increment=1)
                        adjustment.connect('value-changed', lambda a,c=c: self.update_ctrl(c, a.get_value()))
                        scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, hexpand=True, halign=Gtk.Align.END,
                            digits=0, has_origin=False, draw_value=True, value_pos=Gtk.PositionType.LEFT, adjustment=adjustment, width_request=264)
                        if c.zeroer:
                            for controller in scale.observe_controllers():
                                if isinstance(controller, gi.repository.Gtk.GestureClick):
                                    controller.connect('released', lambda c, n, x, y, sc=scale: sc.set_value(0))
                                if isinstance(controller, gi.repository.Gtk.EventControllerKey):
                                    controller.connect('key-pressed', self.handle_ptz_speed_key_pressed)
                                    controller.connect('key-released', self.handle_ptz_speed_key_released)
                        if c.step and c.step != 1:
                            adjustment_step = Gtk.Adjustment(lower=c.min, upper=c.max, value=c.value, step_increment=c.step)
                            adjustment_step.connect('value-changed', lambda a,c=c,a1=adjustment: [a.set_value(a.get_value() - a.get_value() % c.step),a1.set_value(a.get_value())])
                            scale.set_adjustment(adjustment_step)
                        if c.step_big:
                            scale.get_adjustment().set_page_increment(c.step_big)
                        if c.scale_class:
                            scale.add_css_class(c.scale_class)
                        if c.format_value:
                            scale.set_format_value_func(c.format_value)

                        if c.default is not None:
                            scale.add_mark(value=c.default, position=Gtk.PositionType.BOTTOM, markup=None)

                        if c.text_id == 'zoom_absolute':
                            self.zoom_absolute_sc = scale

                        if c.text_id == 'pan_speed':
                            self.pan_speed_sc = scale

                        if c.text_id == 'tilt_speed':
                            self.tilt_speed_sc = scale

                        if c.text_id == 'pan_absolute':
                            self.pan_absolute_sc = scale

                        if c.text_id == 'tilt_absolute':
                            self.tilt_absolute_sc = scale

                        if c.text_id in ['pan_absolute', 'tilt_absolute']:
                            for controller in scale.observe_controllers():
                                if isinstance(controller, gi.repository.Gtk.EventControllerKey):
                                    controller.connect('key-pressed', self.handle_ptz_absolute_key_pressed)

                        refresh = Gtk.Button(icon_name='edit-undo-symbolic', valign=Gtk.Align.CENTER, halign=Gtk.Align.START, has_frame=False)
                        refresh.connect('clicked', lambda e, c=c, sc=scale: sc.get_adjustment().set_value(c.default))
                        ctrl_box.append(refresh)
                        scale_stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT, transition_duration=500)
                        scale_box = Gtk.Box(halign=Gtk.Align.END)
                        spin_box = Gtk.Box(halign=Gtk.Align.END)
                        prev_button = Gtk.Button(icon_name='go-previous-symbolic', has_frame=False, opacity=0.2)
                        prev_button.connect('clicked', lambda e, st=scale_stack, sc=scale_box: st.set_visible_child(sc))
                        next_button = Gtk.Button(icon_name='go-next-symbolic', has_frame=False, opacity=0.2)
                        next_button.connect('clicked', lambda e, st=scale_stack, sp=spin_box: st.set_visible_child(sp))
                        scale_box.append(scale)
                        scale_box.append(next_button)
                        spin = Gtk.SpinButton(adjustment=scale.get_adjustment())
                        spin_box.append(spin)
                        spin_box.append(prev_button)
                        scale_stack.add_child(scale_box)
                        scale_stack.add_child(spin_box)
                        ctrl_box.append(scale_stack)
                        c.gui_value_set = scale.set_value
                        c.gui_ctrls += [scale, spin, refresh]
                        c.gui_default_btn = refresh

                    elif c.type == 'boolean':
                        switch = Gtk.Switch(valign=Gtk.Align.CENTER, active=c.value, margin_end=5, hexpand=True, halign=Gtk.Align.END)
                        switch.connect('state-set', lambda w,state,c=c: self.update_ctrl(c, state))
                        refresh = Gtk.Button(icon_name='edit-undo-symbolic', valign=Gtk.Align.CENTER, halign=Gtk.Align.START, has_frame=False)
                        if c.default is not None:
                            refresh.connect('clicked', lambda e,switch=switch,c=c: switch.set_active(c.default))
                        ctrl_box.append(refresh)
                        ctrl_box.append(switch)
                        c.gui_value_set = switch.set_active
                        c.gui_ctrls += [switch, refresh]
                        c.gui_default_btn = refresh

                    elif c.type == 'button':
                        filtered_menu = [m for m in c.menu if m.value is not None and not m.gui_hidden]
                        children_per_line = min(len(filtered_menu), 4)
                        box = Gtk.FlowBox(orientation=Gtk.Orientation.HORIZONTAL, homogeneous=True,
                                        min_children_per_line=children_per_line, max_children_per_line=children_per_line,
                                        selection_mode=Gtk.SelectionMode.NONE, hexpand=True,
                                        # halign=Gtk.Align.END
                                        # GTK4 workaround
                                        halign=Gtk.Align.FILL if len(filtered_menu) > 4 else Gtk.Align.END)
                        box.set_filter_func(lambda child: child.set_focusable(False) or True)
                        refresh = Gtk.Button(icon_name='edit-undo-symbolic', valign=Gtk.Align.CENTER, halign=Gtk.Align.START, has_frame=False)
                        ctrl_box.append(refresh)
                        ctrl_box.append(box)
                        for m in filtered_menu:
                            b = Gtk.Button(label=m.name, valign=Gtk.Align.CENTER)
                            b.connect('clicked', lambda e, c=c, m=m: self.update_ctrl(c, m.text_id))
                            if c.child_tooltip:
                                b.set_tooltip_markup(c.child_tooltip)
                            if m.lp_text_id is not None:
                                lp = Gtk.GestureLongPress(propagation_phase=Gtk.PropagationPhase.CAPTURE)
                                lp.connect('pressed', lambda lp, x, y, c=c, m=m, b=b: [
                                    lp.set_state(Gtk.EventSequenceState.CLAIMED),
                                    self.update_ctrl(c, m.lp_text_id)
                                ])
                                b.add_controller(lp)
                            box.append(b)
                            c.gui_ctrls += b
                        if c.default is not None:
                            refresh.connect('clicked', lambda e,c=c: self.update_ctrl(c, c.default))
                        c.gui_ctrls += [refresh]
                        c.gui_default_btn = refresh

                    elif c.type == 'info':
                        label = Gtk.Label(label=c.value, selectable=True, justify=Gtk.Justification.RIGHT, hexpand=True,
                                            halign=Gtk.Align.END, wrap=True, wrap_mode=Pango.WrapMode.CHAR,
                                            max_width_chars=48, width_chars=32, xalign=1,
                                            natural_wrap_mode=Gtk.NaturalWrapMode.INHERIT)
                        ctrl_box.append(label)
                        c.gui_value_set = label.set_label
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
                            if c.default is not None:
                                refresh.connect('clicked', lambda e,c=c: find_by_text_id(c.menu, c.default).gui_rb.set_active(True))
                            ctrl_box.append(refresh)
                            ctrl_box.append(box)
                            c.gui_value_set = lambda ctext, c=c: find_by_text_id(c.menu, ctext).gui_rb.set_active(True)
                            c.gui_ctrls += [m.gui_rb for m in c.menu] + [refresh]
                            c.gui_default_btn = refresh
                        else:
                            wb_dd = Gtk.DropDown(model=Gtk.StringList(), valign=Gtk.Align.CENTER, hexpand=True, halign=Gtk.Align.END)
                            for m in c.menu:
                                wb_dd.get_model().append(m.name)
                            if c.value:
                                idx = find_idx(c.menu, lambda m: m.text_id == c.value)
                                if idx is not None:
                                    wb_dd.set_selected(idx)
                                else:
                                    wb_dd.set_selected(Gtk.INVALID_LIST_POSITION)
                                    err = f'Control {c.text_id}: Can\'t find {c.value} in {[m.text_id for m in c.menu]}'
                                    logging.warning(err)
                                    self.notify(err)
                            wb_dd.connect('notify::selected', lambda e,_,c=c: GLib.idle_add(self.update_ctrl, c, c.menu[e.get_selected()].text_id))
                            refresh = Gtk.Button(icon_name='edit-undo-symbolic', valign=Gtk.Align.CENTER, halign=Gtk.Align.START, has_frame=False)
                            if c.default is not None:
                                refresh.connect('clicked', lambda e,c=c,wb_dd=wb_dd: wb_dd.set_selected(find_idx(c.menu, lambda m: m.text_id == c.default)))
                            ctrl_box.append(refresh)
                            ctrl_box.append(wb_dd)
                            c.gui_value_set = lambda ctext, c=c, wb_dd=wb_dd: wb_dd.set_selected(find_idx(c.menu, lambda m: m.text_id == ctext))
                            c.gui_ctrls += [wb_dd, refresh]
                            c.gui_default_btn = refresh

        self.update_ctrls_state()
        _, natsize = self.get_preferred_size()
        self.set_default_size(natsize.width, natsize.height)

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
        # only update if out of sync (when new value comes from the gui)
        if ctrl.value != value:
            errs = []
            self.camera.setup_ctrls({ctrl.text_id: value}, errs)
            if errs:
                self.notify('\n'.join(errs))
                GLib.idle_add(self.update_ctrl_value, ctrl),
                return

        self.update_ctrls_state()
        if ctrl.reopener:
            GLib.idle_add(self.reopen_device)

    def update_ctrls_state(self):
        for c in self.camera.get_ctrls():
            self.update_ctrl_state(c)

    def update_ctrl_state(self, c):
        for gui_ctrl in c.gui_ctrls:
            gui_ctrl.set_sensitive(not c.inactive and not c.readonly)
        if c.gui_default_btn is not None:
            visible = not c.inactive and not c.readonly and (
                c.default is not None and c.value is not None and c.default != c.value or \
                c.get_default is not None and not c.get_default()
            )
            c.gui_default_btn.set_opacity(visible)
            c.gui_default_btn.set_can_focus(visible)

    def update_ctrl_value(self, c):
        if c.reopener:
            self.reopen_device()
            return
        if c.gui_value_set:
            c.gui_value_set(c.value)
        self.update_ctrl_state(c)

    def handle_ptz_speed_key_pressed(self, c, keyval, keycode, state):
        pan_lower = self.pan_speed_sc.get_adjustment().get_lower()
        pan_upper =self.pan_speed_sc.get_adjustment().get_upper()
        tilt_lower = self.tilt_speed_sc.get_adjustment().get_lower()
        tilt_upper = self.tilt_speed_sc.get_adjustment().get_upper()

        if keyval in [Gdk.KEY_Left, Gdk.KEY_KP_Left, Gdk.KEY_a]:
            self.pan_speed_sc.set_value(pan_lower)
        elif keyval in [Gdk.KEY_Right, Gdk.KEY_KP_Right, Gdk.KEY_d]:
            self.pan_speed_sc.set_value(pan_upper)
        elif keyval in [Gdk.KEY_Up, Gdk.KEY_KP_Up, Gdk.KEY_w]:
            self.tilt_speed_sc.set_value(tilt_upper)
        elif keyval in [Gdk.KEY_Down, Gdk.KEY_KP_Down, Gdk.KEY_s]:
            self.tilt_speed_sc.set_value(tilt_lower)
        elif keyval == Gdk.KEY_KP_End:
            self.pan_speed_sc.set_value(pan_lower)
            self.tilt_speed_sc.set_value(tilt_lower)
        elif keyval == Gdk.KEY_KP_Page_Down:
            self.pan_speed_sc.set_value(pan_upper)
            self.tilt_speed_sc.set_value(tilt_lower)
        elif keyval == Gdk.KEY_KP_Home:
            self.pan_speed_sc.set_value(pan_lower)
            self.tilt_speed_sc.set_value(tilt_upper)
        elif keyval == Gdk.KEY_KP_Page_Up:
            self.pan_speed_sc.set_value(pan_upper)
            self.tilt_speed_sc.set_value(tilt_upper)
        elif self.zoom_absolute_sc is not None:
            return self.handle_ptz_key_pressed_zoom(keyval, state)
        else:
            return False
        return True

    def handle_ptz_absolute_key_pressed(self, c, keyval, keycode, state):
        pan_value = self.pan_absolute_sc.get_value()
        pan_step = self.pan_absolute_sc.get_adjustment().get_step_increment()
        tilt_value = self.tilt_absolute_sc.get_value()
        tilt_step = self.tilt_absolute_sc.get_adjustment().get_step_increment()
    
        if keyval in [Gdk.KEY_Left, Gdk.KEY_KP_Left, Gdk.KEY_a]:
            self.pan_absolute_sc.set_value(pan_value - pan_step)
        elif keyval in [Gdk.KEY_Right, Gdk.KEY_KP_Right, Gdk.KEY_d]:
            self.pan_absolute_sc.set_value(pan_value + pan_step)
        elif keyval in [Gdk.KEY_Up, Gdk.KEY_KP_Up, Gdk.KEY_w]:
            self.tilt_absolute_sc.set_value(tilt_value + tilt_step)
        elif keyval in [Gdk.KEY_Down, Gdk.KEY_KP_Down, Gdk.KEY_s]:
            self.tilt_absolute_sc.set_value(tilt_value - tilt_step)
        elif keyval == Gdk.KEY_KP_End:
            self.pan_absolute_sc.set_value(pan_value - pan_step)
            self.tilt_absolute_sc.set_value(tilt_value - tilt_step)
        elif keyval == Gdk.KEY_KP_Page_Down:
            self.pan_absolute_sc.set_value(pan_value + pan_step)
            self.tilt_absolute_sc.set_value(tilt_value - tilt_step)
        elif keyval == Gdk.KEY_KP_Home:
            self.pan_absolute_sc.set_value(pan_value - pan_step)
            self.tilt_absolute_sc.set_value(tilt_value + tilt_step)
        elif keyval == Gdk.KEY_KP_Page_Up:
            self.pan_absolute_sc.set_value(pan_value + pan_step)
            self.tilt_absolute_sc.set_value(tilt_value + tilt_step)
        elif keyval == Gdk.KEY_KP_Insert:
            self.pan_absolute_sc.set_value(0)
            self.tilt_absolute_sc.set_value(0)
        elif self.zoom_absolute_sc is not None:
            return self.handle_ptz_key_pressed_zoom(keyval, state)
        else:
            return False
        return True

    def handle_ptz_key_pressed_zoom(self, keyval, state):
        zoom_value = self.zoom_absolute_sc.get_value()
        zoom_step = self.zoom_absolute_sc.get_adjustment().get_step_increment()
        zoom_page = self.zoom_absolute_sc.get_adjustment().get_page_increment()
        zoom_lower = self.zoom_absolute_sc.get_adjustment().get_lower()
        zoom_upper = self.zoom_absolute_sc.get_adjustment().get_upper()

        if keyval in [Gdk.KEY_plus, Gdk.KEY_KP_Add] and state & Gdk.ModifierType.CONTROL_MASK:
            self.zoom_absolute_sc.set_value(zoom_value + zoom_page)
        elif keyval in [Gdk.KEY_minus, Gdk.KEY_KP_Subtract] and state & Gdk.ModifierType.CONTROL_MASK:
            self.zoom_absolute_sc.set_value(zoom_value - zoom_page)
        elif keyval in [Gdk.KEY_plus, Gdk.KEY_KP_Add]:
            self.zoom_absolute_sc.set_value(zoom_value + zoom_step)
        elif keyval in [Gdk.KEY_minus, Gdk.KEY_KP_Subtract]:
            self.zoom_absolute_sc.set_value(zoom_value - zoom_step)
        elif keyval in [Gdk.KEY_Home]:
            self.zoom_absolute_sc.set_value(zoom_lower)
        elif keyval in [Gdk.KEY_End]:
            self.zoom_absolute_sc.set_value(zoom_upper)
        elif keyval in [Gdk.KEY_Page_Up]:
            self.zoom_absolute_sc.set_value(zoom_value + zoom_page)
        elif keyval in [Gdk.KEY_Page_Down]:
            self.zoom_absolute_sc.set_value(zoom_value - zoom_page)
        else:
            return False
        return True

    def handle_ptz_speed_key_released(self, c, keyval, keycode, state):
        if keyval in [Gdk.KEY_Left, Gdk.KEY_Right, Gdk.KEY_KP_Left, Gdk.KEY_KP_Right, Gdk.KEY_a, Gdk.KEY_d]:
            self.pan_speed_sc.set_value(0)
        elif keyval in [Gdk.KEY_Up, Gdk.KEY_Down, Gdk.KEY_KP_Up, Gdk.KEY_KP_Down, Gdk.KEY_w, Gdk.KEY_s]:
            self.tilt_speed_sc.set_value(0)
        elif keyval in [Gdk.KEY_KP_End, Gdk.KEY_KP_Page_Down, Gdk.KEY_KP_Home, Gdk.KEY_KP_Page_Up]:
            self.pan_speed_sc.set_value(0)
            self.tilt_speed_sc.set_value(0)
        else:
            return False
        return True

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
        about.set_copyright('Copyright © 2022 - 2024 Gergo Koteles')
        about.set_license_type(Gtk.License.GPL_3_0)
        about.set_logo_icon_name('hu.irl.cameractrls')
        about.set_website(ghurl)
        about.set_website_label('GitHub')
        about.set_version(version)
        about.present()

    def on_quit(self, action, param):
        self.window.close()

    def check_preview_open(self, p):
        # if process returned
        if p.poll() is not None:
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
