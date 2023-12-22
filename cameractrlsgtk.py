#!/usr/bin/env python3

import os, sys, logging, subprocess
import gi
from cameractrls import CameraCtrls, find_by_text_id, get_devices, v4ldirs, find_idx
from cameractrls import version, ghurl

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gio, GLib, Pango, Gdk, GObject

class GStr(GObject.GObject):
    def __init__(self, text):
        GObject.GObject.__init__(self)
        self.text = text
    def __str__(self):
        return self.text

class FormatScale(Gtk.Scale):
    def __init__(self, format_value = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.format_value = format_value

    def do_format_value(self, v):
        if self.format_value:
            return self.format_value(self, v)
        return f'{v:.0f}'

class CameraCtrlsWindow(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, type_hint=Gdk.WindowTypeHint.DIALOG, **kwargs)
        self.devices = []
        
        self.fd = 0
        self.device = None
        self.camera = None
        self.listener = None

        self.grid = None
        self.frame = None
        self.device_cb = None

        self.zoom_absolute = None
        self.pan_speed_sc = None
        self.tilt_speed_sc = None

        self.init_window()
        self.refresh_devices()

    def init_window(self):
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b'''
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
            image=Gtk.Image(icon_name='open-menu-symbolic', icon_size=Gtk.IconSize.MENU),
            relief=Gtk.ReliefStyle.NONE,
        )

        self.open_cam_button = Gtk.Button(
            action_name='app.open_camera_window',
            action_target=GLib.Variant('s', ''),
            image=Gtk.Image(icon_name='camera-video-symbolic', icon_size=Gtk.IconSize.MENU),
            relief=Gtk.ReliefStyle.NONE,
        )

        refresh_button = Gtk.Button(
            image=Gtk.Image(icon_name='view-refresh-symbolic', icon_size=Gtk.IconSize.MENU),
            relief=Gtk.ReliefStyle.NONE,
        )
        refresh_button.connect('clicked', lambda e: self.refresh_devices())

        headerbar = Gtk.HeaderBar(title='Cameractrls', show_close_button=True)
        headerbar.pack_start(refresh_button)
        headerbar.pack_end(hamburger_button)
        headerbar.pack_end(self.open_cam_button)

        self.grid = Gtk.Grid()

        self.zero_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, halign=Gtk.Align.CENTER)
        self.zero_box.pack_start(Gtk.Image(icon_name='camera-disabled-symbolic', icon_size=Gtk.IconSize.DIALOG, pixel_size=96,
                                            margin_top=30, margin_bottom=10, margin_start=80, margin_end=80), True, True, 0)
        self.zero_box.pack_start(Gtk.Label(label='<span size="17000" color="gray">0 camera found</span>', use_markup=True,
                                            margin_top=10, margin_bottom=20), True, True, 0)
        if 'SNAP' in os.environ:
            self.zero_box.pack_start(Gtk.Label(label='Please permit access with', max_width_chars=30, wrap=True, margin_top=10), True, True, 0)
            self.zero_box.pack_start(Gtk.Label(label='snap connect cameractrls:camera', selectable=True, margin_bottom=10), True, True, 0)
        self.zero_box.show_all()
        self.zero_box.set_no_show_all(True)

        self.model = Gio.ListStore()
        self.device_lb = Gtk.ListBox(activate_on_single_click=True, selection_mode=Gtk.SelectionMode.SINGLE, margin=5)
        self.device_lb.bind_model(self.model, lambda i: Gtk.Label(label=i.text, margin=10, xalign=0))
        self.device_lb.show_all()
        # row-selected fires at every popover open so only row-activated used
        self.device_lb.connect('row-activated', lambda lb, r: [
            self.gui_open_device(r.get_index()),
            self.device_sw.get_popover().popdown(),
        ])

        self.device_sw = Gtk.MenuButton(
            popover=Gtk.Popover(position=Gtk.PositionType.BOTTOM, child=self.device_lb),
            image=Gtk.Image(icon_name='view-more-symbolic', icon_size=Gtk.IconSize.MENU),
            relief=Gtk.ReliefStyle.NONE,
        )
        headerbar.pack_start(self.device_sw)

        headerbar.show_all()
        self.set_titlebar(headerbar)

        self.grid.attach(self.zero_box, 0, 0, 1, 1)
        self.grid.show()

        self._notify_timeout = None

        overlay = Gtk.Overlay()
        overlay.add(self.grid)

        # Notification overlay widget
        self._revealer = Gtk.Revealer(valign=Gtk.Align.END, halign=Gtk.Align.CENTER)
        self._notify_label = Gtk.Label(wrap=True, wrap_mode=Pango.WrapMode.CHAR)
        self._notify_label .get_style_context().add_class('app-notification')
        self._revealer.add(self._notify_label)
        overlay.add_overlay(self._revealer)
        overlay.set_overlay_pass_through(self._revealer, True)
        overlay.show_all()

        self.add(overlay)

        self.connect('delete-event', lambda w,e: self.close_device())

    def refresh_devices(self):
        logging.info('refresh_devices')
        self.devices = get_devices(v4ldirs)
        
        if len(self.devices) == 0:
            self.close_device()
            self.init_gui_device()

        self.model.splice(0, self.model.get_n_items(), [GStr(d.name) for d in self.devices])

        if len(self.devices):
            idx = 0
            if self.device in self.devices:
                idx = self.devices.index(self.device)
            self.device_lb.select_row(self.device_lb.get_row_at_index(idx))
            self.gui_open_device(idx)

        if len(self.devices) == 0:
            self.zero_box.set_visible(True)
            self.device_sw.set_visible(False)
            self.open_cam_button.set_visible(False)
        else:
            self.zero_box.set_visible(False)
            self.device_sw.set_visible(True)
            self.open_cam_button.set_visible(True)

    def gui_open_device(self, id):
        logging.info('gui_open_device')
        # if the selection is empty (after remove_all)
        if id == -1:
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
        self.open_cam_button.set_action_target_value(GLib.Variant('s', self.device.path))

    def close_device(self):
        if self.fd:
            logging.info('close_device')    
            self.device = None
            self.camera = None
            self.listener.stop()
            self.listener = None
            os.close(self.fd)
            self.fd = 0

    def init_gui_device(self):
        logging.info('init_gui_device')
        if self.frame:
            self.frame.destroy()
            # forget old size
            self.resize(1,1)

        if self.device is None:
            return

        self.frame = Gtk.Grid(hexpand=True, halign=Gtk.Align.FILL)
        self.grid.attach(self.frame, 0, 0, 1, 1)

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
                ctrls_listbox.set_header_func(lambda row, before: row.set_header(Gtk.Separator()) if before is not None else None)
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
                    c.gui_value_set = None

                    if c.type == 'integer':
                        adjustment = Gtk.Adjustment(lower=c.min, upper=c.max, value=c.value, step_increment=1)
                        adjustment.connect('value-changed', lambda a,c=c: self.update_ctrl(c, a.get_value()))
                        scale = FormatScale(c.format_value, orientation=Gtk.Orientation.HORIZONTAL,
                            digits=0, has_origin=False, value_pos=Gtk.PositionType.LEFT, adjustment=adjustment, width_request=264)
                        if c.zeroer:
                            scale.connect('button-release-event', lambda sc, e: sc.set_value(0))
                            scale.connect('key-press-event', self.handle_ptz_key_pressed)
                            scale.connect('key-release-event', self.handle_ptz_key_released)
                        if c.step and c.step != 1:
                            adjustment_step = Gtk.Adjustment(lower=c.min, upper=c.max, value=c.value, step_increment=c.step)
                            adjustment_step.connect('value-changed', lambda a,c=c,a1=adjustment: [a.set_value(a.get_value() - a.get_value() % c.step),a1.set_value(a.get_value())])
                            scale.set_adjustment(adjustment_step)
                        if c.step_big:
                            scale.get_adjustment().set_page_increment(c.step_big)
                        if c.scale_class:
                            scale.get_style_context().add_class(c.scale_class)

                        if c.default is not None:
                            scale.add_mark(value=c.default, position=Gtk.PositionType.BOTTOM, markup=None)

                        if c.text_id == 'zoom_absolute':
                            self.zoom_absolute_sc = scale

                        if c.text_id == 'pan_speed':
                            self.pan_speed_sc = scale

                        if c.text_id == 'tilt_speed':
                            self.tilt_speed_sc = scale

                        refresh = Gtk.Button(image=Gtk.Image(icon_name='edit-undo-symbolic', icon_size=Gtk.IconSize.BUTTON), valign=Gtk.Align.CENTER, halign=Gtk.Align.START, relief=Gtk.ReliefStyle.NONE)
                        refresh.connect('clicked', lambda e, c=c, sc=scale: sc.get_adjustment().set_value(c.default))
                        ctrl_box.pack_start(refresh, False, False, 0)
                        ctrl_box.pack_end(scale, False, False, 0)
                        c.gui_value_set = scale.set_value
                        c.gui_ctrls += [scale, refresh]
                        c.gui_default_btn = refresh

                    elif c.type == 'boolean':
                        switch = Gtk.Switch(valign=Gtk.Align.CENTER, active=c.value, margin_right=5)
                        switch.connect('state-set', lambda w,state,c=c: self.update_ctrl(c, state))
                        refresh = Gtk.Button(image=Gtk.Image(icon_name='edit-undo-symbolic', icon_size=Gtk.IconSize.BUTTON), valign=Gtk.Align.CENTER, halign=Gtk.Align.START, relief=Gtk.ReliefStyle.NONE)
                        if c.default is not None:
                            refresh.connect('clicked', lambda e,switch=switch,c=c: switch.set_active(c.default))
                        ctrl_box.pack_start(refresh, False, False, 0)
                        ctrl_box.pack_end(switch, False, False, 0)
                        c.gui_value_set = switch.set_active
                        c.gui_ctrls += [switch, refresh]
                        c.gui_default_btn = refresh

                    elif c.type == 'button':
                        filtered_menu = [m for m in c.menu if m.value is not None and not m.gui_hidden]
                        children_per_line = min(len(filtered_menu), 4)
                        box = Gtk.FlowBox(orientation=Gtk.Orientation.HORIZONTAL, homogeneous=True,
                                        min_children_per_line=children_per_line, max_children_per_line=children_per_line,
                                        selection_mode=Gtk.SelectionMode.NONE)
                        box.set_filter_func(lambda child: child.set_can_focus(False) or True)
                        refresh = Gtk.Button(image=Gtk.Image(icon_name='edit-undo-symbolic', icon_size=Gtk.IconSize.BUTTON), valign=Gtk.Align.CENTER, halign=Gtk.Align.START, relief=Gtk.ReliefStyle.NONE)
                        ctrl_box.pack_start(refresh, False, False, 0)
                        ctrl_box.pack_end(box, False, False, 0)
                        for m in filtered_menu:
                            b = Gtk.Button(label=m.name, valign=Gtk.Align.CENTER)
                            b.connect('clicked', lambda e, c=c, m=m: self.update_ctrl(c, m.text_id))
                            if m.lp_text_id is not None:
                                m.gui_lp = Gtk.GestureLongPress(widget=b)
                                m.gui_lp.connect('pressed', lambda lp, x, y, c=c, m=m, b=b: [
                                    lp.set_state(Gtk.EventSequenceState.CLAIMED),
                                    self.update_ctrl(c, m.lp_text_id)
                                ])
                            box.add(b)
                            c.gui_ctrls += b
                        if c.default is not None:
                            refresh.connect('clicked', lambda e,c=c: self.update_ctrl(c, c.default))
                        c.gui_ctrls += [refresh]
                        c.gui_default_btn = refresh

                    elif c.type == 'info':
                        label = Gtk.Label(label=c.value, selectable=True, justify=Gtk.Justification.RIGHT,
                                            wrap=True, wrap_mode=Pango.WrapMode.CHAR,
                                            max_width_chars=48, width_chars=32, xalign=1)
                        ctrl_box.pack_end(label, False, False, 0)
                        c.gui_value_set = label.set_label
                        c.gui_default_btn = None

                    elif c.type == 'menu':
                        if len(c.menu) < 4 and not c.menu_dd:
                            box = Gtk.ButtonBox(valign=Gtk.Align.CENTER)
                            box.set_layout(Gtk.ButtonBoxStyle.EXPAND)
                            box.set_homogeneous(False)
                            rb = None
                            for m in c.menu:
                                rb = Gtk.RadioButton(group=rb, label=m.name)
                                rb.set_mode(False)
                                rb.set_active(m.text_id == c.value)
                                rb.connect('toggled', lambda b, c=c, m=m: self.update_ctrl(c, m.text_id) if b.get_active() else None)
                                box.add(rb)
                                m.gui_rb = rb
                            if c.value is None:
                                rb = Gtk.RadioButton(group=rb, label='Undefined')
                                rb.set_mode(False)
                                rb.set_active(True)
                                rb.set_no_show_all(True)
                                box.add(rb)

                            refresh = Gtk.Button(image=Gtk.Image(icon_name='edit-undo-symbolic', icon_size=Gtk.IconSize.BUTTON), valign=Gtk.Align.CENTER, halign=Gtk.Align.START, relief=Gtk.ReliefStyle.NONE)
                            if c.default is not None:
                                refresh.connect('clicked', lambda e,c=c: find_by_text_id(c.menu, c.default).gui_rb.set_active(True))
                            ctrl_box.pack_start(refresh, False, False, 0)
                            ctrl_box.pack_end(box, False, False, 0)
                            c.gui_value_set = lambda ctext, c=c: find_by_text_id(c.menu, ctext).gui_rb.set_active(True)
                            c.gui_ctrls += [m.gui_rb for m in c.menu] + [refresh]
                            c.gui_default_btn = refresh
                        else:
                            wb_cb = Gtk.ComboBoxText(valign=Gtk.Align.CENTER)
                            for m in c.menu:
                                wb_cb.append_text(m.name)
                            if c.value:
                                idx = find_idx(c.menu, lambda m: m.text_id == c.value)
                                if idx is not None:
                                    wb_cb.set_active(idx)
                                else:
                                    err = f'Control {c.text_id}: Can\'t find {c.value} in {[m.text_id for m in c.menu]}'
                                    logging.warning(err)
                                    self.notify(err)
                            wb_cb.connect('changed', lambda e,c=c: GLib.idle_add(self.update_ctrl, c, c.menu[e.get_active()].text_id))
                            refresh = Gtk.Button(image=Gtk.Image(icon_name='edit-undo-symbolic', icon_size=Gtk.IconSize.BUTTON), valign=Gtk.Align.CENTER, halign=Gtk.Align.START, relief=Gtk.ReliefStyle.NONE)
                            if c.default is not None:
                                refresh.connect('clicked', lambda e,c=c,wb_cb=wb_cb: wb_cb.set_active(find_idx(c.menu, lambda m: m.text_id == c.default)))
                            ctrl_box.pack_start(refresh, False, False, 0)
                            ctrl_box.pack_end(wb_cb, False, False, 0)
                            c.gui_value_set = lambda ctext, c=c, wb_cb=wb_cb: wb_cb.set_active(find_idx(c.menu, lambda m: m.text_id == ctext))
                            c.gui_ctrls += [wb_cb, refresh]
                            c.gui_default_btn = refresh

        self.update_ctrls_state()
        self.grid.show_all()

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

        self.update_ctrls_state()
        if ctrl.reopener:
            self.reopen_device()

    def update_ctrls_state(self):
        for c in self.camera.get_ctrls():
            self.update_ctrl_state(c)

    def update_ctrl_state(self, c):
        for gui_ctrl in c.gui_ctrls:
            gui_ctrl.set_sensitive(not c.inactive)
        if c.gui_default_btn is not None:
            visible = not c.inactive and (
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

    def handle_ptz_key_pressed(self, w, e):
        keyval = e.keyval
        state = e.state
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
            zoom_value = self.zoom_absolute_sc.get_value()
            zoom_step = self.zoom_absolute_sc.get_adjustment().get_step_increment()
            zoom_page = self.zoom_absolute_sc.get_adjustment().get_page_increment()
            zoom_lower = self.zoom_absolute_sc.get_adjustment().get_lower()
            zoom_upper = self.zoom_absolute_sc.get_adjustment().get_upper()

            if keyval in [Gdk.KEY_plus, Gdk.KEY_KP_Add] and state == Gdk.ModifierType.CONTROL_MASK:
                self.zoom_absolute_sc.set_value(zoom_value + zoom_page)
            elif keyval in [Gdk.KEY_minus, Gdk.KEY_KP_Subtract] and state == Gdk.ModifierType.CONTROL_MASK:
                self.zoom_absolute_sc.set_value(zoom_value - zoom_page)
            elif keyval in [Gdk.KEY_plus, Gdk.KEY_KP_Add]:
                self.zoom_absolute_sc.set_value(zoom_value + zoom_step)
            elif keyval in [Gdk.KEY_minus, Gdk.KEY_KP_Subtract]:
                self.zoom_absolute_sc.set_value(zoom_value - zoom_step)
            elif keyval in [Gdk.KEY_Home]:
                self.zoom_absolute_sc.set_value(zoom_lower)
            elif keyval in [Gdk.KEY_End]:
                self.zoom_absolute_sc.set_value(zoom_upper)
            else:
                return False
        else:
            return False
        return True

    def handle_ptz_key_released(self, w, e):
        keyval = e.keyval

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

        icon_theme = Gtk.IconTheme.get_for_screen(Gdk.Screen.get_default())
        icon_theme.append_search_path(f'{sys.path[0]}/pkg')

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
        win_width, win_height = self.window.get_size()
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
