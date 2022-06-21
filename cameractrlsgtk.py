#!/usr/bin/env python3

import os, sys, logging
import gi
from cameractrls import CameraCtrls, find_by_text_id, get_devices, v4ldirs, find_idx
from cameractrls import version, ghurl

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk

class CameraCtrlsGui:
    def __init__(self):
        self.devices = []
        
        self.fd = 0
        self.device = ''
        self.camera = None

        self.cnt=0

        self.window = None
        self.kpsmallimg = None
        self.grid = None
        self.frame = None
        self.device_cb = None

        self.init_window()
        self.refresh_devices()

    def init_window(self):
        self.window = Gtk.Window(title='Cameractrls', type_hint=Gdk.WindowTypeHint.DIALOG)
        self.window.connect('destroy', Gtk.main_quit)
        self.window.set_default_icon_from_file(f'{sys.path[0]}/images/icon_256.png')

        headerbar = Gtk.HeaderBar(title='Cameractrls', show_close_button=True)
        self.window.set_titlebar(headerbar)

        hamburger = Gtk.MenuButton()
        hamburger_icon = Gtk.Image.new_from_icon_name("open-menu-symbolic", Gtk.IconSize.MENU)
        hamburger.add(hamburger_icon)

        popover = Gtk.Popover(position=Gtk.PositionType.BOTTOM)
        menu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin=10, spacing=10)
        about_elem = Gtk.Button(label='About', relief=Gtk.ReliefStyle.NONE)
        about_elem.connect('clicked', lambda e,p=popover: [self.open_about(), p.popdown()])
        menu.pack_start(about_elem, True, True, 0)
        menu.show_all()
        popover.add(menu)

        hamburger.set_popover(popover)
        headerbar.pack_end(hamburger)

        self.grid = Gtk.Grid()

        self.zero_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, halign=Gtk.Align.CENTER)
        zero_label = Gtk.Label(label='0 camera found')
        zero_refresh = Gtk.Button(label='Refresh')
        zero_refresh.connect('clicked', lambda e: self.refresh_devices())
        self.zero_box.pack_start(zero_label, True, True, 10)
        self.zero_box.pack_start(zero_refresh, True, True, 5)
        self.zero_box.show_all()

        self.device_box = Gtk.Box(halign=Gtk.Align.CENTER, hexpand=True)
        self.device_cb = Gtk.ComboBoxText(margin_top=10)
        self.device_cb.connect('changed', lambda e: self.gui_open_device(self.device_cb.get_active()))
        self.device_box.pack_start(self.device_cb, True, True, 0)
        self.device_box.show_all()

        self.grid.attach(self.zero_box, 0, 0, 1, 1)
        self.window.add(self.grid)

    def open_about(self):
        about = Gtk.AboutDialog(transient_for=self.window, modal=self.window)
        about.set_program_name('Cameractrls')
        about.set_authors(['Gergo Koteles <soyer@irl.hu>'])
        about.set_copyright('Copyright © 2022 Gergo Koteles')
        about.set_license_type(Gtk.License.MIT_X11)
        about.set_website(ghurl)
        about.set_website_label('GitHub')
        about.set_version(version)
        about.connect('response', lambda d, r: d.destroy())
        about.present()

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

        if len(self.devices) == 0 and self.device_box.get_parent() != None:
            self.grid.remove(self.device_box)
            self.grid.attach(self.zero_box, 0, 0, 1, 1)
        elif len(self.devices) != 0 and self.zero_box.get_parent() != None:
            self.grid.remove(self.zero_box)
            self.grid.attach(self.device_box, 0, 0, 1, 1)

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
            self.window.resize(1,1)
        
        if self.device == '':
            return

        self.frame = Gtk.Grid(hexpand=True, halign=Gtk.Align.FILL)
        self.grid.attach(self.frame, 0, 1, 1, 1)

        
        stack_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin=10, vexpand=True, halign=Gtk.Align.CENTER)
        stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT, transition_duration=500)
        stack_sw = Gtk.StackSwitcher(stack=stack, hexpand=True, halign=Gtk.Align.CENTER)
        stack_box.pack_start(stack_sw, False, False, 0)
        stack_box.pack_start(stack, False, False, 0)

        self.frame.attach(stack_box, 0, 1, 1, 1)

        footer = Gtk.Box(margin=10, orientation=Gtk.Orientation.VERTICAL)
        self.frame.attach(footer, 0, 2, 1, 1)

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
                    ctrl_box.pack_start(label, False, False, 0)

                    if c.type == 'integer':
                        adjustment = Gtk.Adjustment(lower=c.min, upper=c.max, value=c.value)
                        adjustment.connect('value-changed', lambda a,c=c: self.update_ctrl(c, a.get_value()))
                        scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL,
                            digits=0, value_pos=Gtk.PositionType.LEFT, adjustment=adjustment, width_request=264)
                        if c.step and c.step != 1:
                            adjustment_step = Gtk.Adjustment(lower=c.min, upper=c.max, value=c.value)
                            adjustment_step.connect('value-changed', lambda a,c=c,a1=adjustment: [a.set_value(a.get_value() - a.get_value() % c.step),a1.set_value(a.get_value())])
                            scale.set_adjustment(adjustment_step)

                        if c.default != None:
                            scale.add_mark(value=c.default, position=Gtk.PositionType.BOTTOM, markup=None)
                        
                        refresh = Gtk.Button(label='⟳', valign=Gtk.Align.CENTER, halign=Gtk.Align.START, relief=Gtk.ReliefStyle.NONE)
                        refresh.connect('clicked', lambda e, c=c, sc=scale: sc.get_adjustment().set_value(c.default))
                        ctrl_box.pack_start(refresh, False, False, 0)
                        ctrl_box.pack_end(scale, False, False, 0)
                        c.gui_ctrls =  [scale, refresh]
                        c.gui_default_btn = refresh

                    elif c.type == 'boolean':
                        switch = Gtk.Switch(valign=Gtk.Align.CENTER, active=c.value, margin_right=5)
                        switch.connect('state-set', lambda a,b,c=c: self.update_ctrl(c, a.get_active()))
                        refresh = Gtk.Button(label='⟳', valign=Gtk.Align.CENTER, halign=Gtk.Align.START, relief=Gtk.ReliefStyle.NONE)
                        if c.default != None:
                            refresh.connect('clicked', lambda e,switch=switch,c=c: switch.set_active(c.default))
                        ctrl_box.pack_start(refresh, False, False, 0)
                        ctrl_box.pack_end(switch, False, False, 0)
                        c.gui_ctrls =  [switch, refresh]
                        c.gui_default_btn = refresh

                    elif c.type == 'button':
                        c.gui_ctrls =  []
                        for m in c.menu:
                            b = Gtk.Button(label=m.name, valign=Gtk.Align.CENTER, margin_right=5)
                            b.connect('clicked', lambda e,c=c: self.update_ctrl(c, m.text_id))
                            ctrl_box.pack_end(b, False, False, 0)
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

                            refresh = Gtk.Button(label='⟳', valign=Gtk.Align.CENTER, halign=Gtk.Align.START, relief=Gtk.ReliefStyle.NONE)
                            if c.default != None:
                                refresh.connect('clicked', lambda e,c=c: find_by_text_id(c.menu, c.default).gui_rb.set_active(True))
                            ctrl_box.pack_start(refresh, False, False, 0)
                            ctrl_box.pack_end(box, False, False, 0)
                            c.gui_ctrls = [m.gui_rb for m in c.menu] + [refresh]
                            c.gui_default_btn = refresh
                        else:
                            wb_cb = Gtk.ComboBoxText(valign=Gtk.Align.CENTER)
                            for m in c.menu:
                                wb_cb.append_text(m.name)
                            if c.value:
                                wb_cb.set_active(find_idx(c.menu, lambda m: m.text_id == c.value))
                            wb_cb.connect('changed', lambda e,c=c: self.update_ctrl(c, c.menu[e.get_active()].text_id))
                            refresh = Gtk.Button(label='⟳', valign=Gtk.Align.CENTER, halign=Gtk.Align.START, relief=Gtk.ReliefStyle.NONE)
                            if c.default != None:
                                refresh.connect('clicked', lambda e,c=c,wb_cb=wb_cb: wb_cb.set_active(find_idx(c.menu, lambda m: m.text_id == c.default)))
                            ctrl_box.pack_start(refresh, False, False, 0)
                            ctrl_box.pack_end(wb_cb, False, False, 0)
                            c.gui_ctrls =  [wb_cb, refresh]
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

    def start(self):
        self.window.show_all()
        Gtk.main()


if __name__ == '__main__':
    gui = CameraCtrlsGui()
    gui.start()
