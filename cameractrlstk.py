#!/usr/bin/env python3

import os, logging, sys, webbrowser, subprocess
from cameractrls import CameraCtrls, get_devices, v4ldirs
from cameractrls import version, ghurl

try:
    from tkinter import Tk, ttk, PhotoImage, IntVar, StringVar, messagebox
except Exception as e:
    logging.error(f'tkinter import failed: {e}, please install the python3-tk package')
    sys.exit(3)

class CameraCtrlsGui:
    def __init__(self):
        self.devices = []
        
        self.fd = 0
        self.device = None
        self.camera = None
        self.listener = None

        self.window = None
        self.frame = None
        self.devicescb = None

        self.child_processes = []

        self.init_window()
        self.refresh_devices()

    def init_window(self):
        self.window = Tk(className='hu.irl.cameractrls')
        self.window.title('Cameractrls')
        self.window.bind('<Control-q>', lambda e: self.close_window())
        self.window.protocol("WM_DELETE_WINDOW", self.close_window)

        s = ttk.Style()
        s.configure('BorderlessShort.TButton', padding=[10,0,10,0], borderwidth=0)
        s.configure('Short.TButton', padding=[10,0,10,0])
        s.map('Horizontal.TScale', background=[('focus', '#aaaaaa')])
        s.map('TCombobox', background=[('focus', '#aaaaaa')])


        head = ttk.Frame(self.window)
        head.grid(row=1, sticky='E')

        ttk.Label(head, text=f'cameractrls {version} | ').grid(row=0, column=0)
        gh = ttk.Label(head, text='GitHub★', foreground='blue', cursor='hand2')
        gh.bind('<Button-1>', lambda e: webbrowser.open(ghurl))
        gh.grid(row=0, column=1)

    def close_window(self):
        self.close_device()
        self.window.destroy()

    def refresh_devices(self):
        self.devices = get_devices(v4ldirs)
        if self.device not in self.devices:
            self.close_device()
            if len(self.devices):
                self.open_device(self.devices[0])
            self.init_gui_device()
        if self.devicescb:
            self.devicescb['values'] = [d.name for d in self.devices]

    def check_preview_open(self, p):
        # if process returned
        if p.poll() != None:
            (stdout, stderr) = p.communicate()
            errstr = str(stderr, 'utf-8')
            sys.stderr.write(errstr)
            if p.returncode != 0:
                messagebox.showwarning(message=errstr.strip())
        else:
            self.window.after(1000, self.check_preview_open, p)

    def open_camera_window(self):
        win_width, win_height = self.window.winfo_width(), self.window.winfo_height()
        logging.info(f'open cameraview.py for {self.device.path} with max size {win_width}x{win_height}')
        p = subprocess.Popen([f'{sys.path[0]}/cameraview.py', '-d', self.device.path, '-s', f'{win_width}x{win_height}'], stderr=subprocess.PIPE)
        self.child_processes.append(p)
        self.window.after(300, self.check_preview_open, p)

    def gui_open_device(self, id):
        logging.info('gui_open_device')
        if id == -1:
            return

        self.close_device()
        self.open_device(self.devices[id])
        self.init_gui_device()

    def reopen_device(self):
        device = self.device
        self.close_device()
        self.open_device(device)
        self.init_gui_device()

    def open_device(self, device):
        logging.info(f'opening device: {device.path}')

        try:
            self.fd = os.open(device.path, os.O_RDWR, 0)
        except Exception as e:
            logging.error(f'os.open({device.path}, os.O_RDWR, 0) failed: {e}')

        self.camera = CameraCtrls(device.path, self.fd)
        self.listener = self.camera.subscribe_events(
            lambda c: self.window.after_idle(self.update_ctrl_value, c),
            lambda errs: self.window.after_idle(lambda errs=errs: messagebox.showwarning(message='\n'.join(errs)))
        )
        self.device = device

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
            self.frame.grid_forget()
            self.frame.destroy()
            self.devicescb = None

        self.frame = ttk.Frame(self.window, padding=10)
        self.frame.grid(row=0)

        if len(self.devices) == 0:
            ttk.Label(self.frame, text='0 camera found', padding=10).grid()
            ttk.Button(self.frame, text='Refresh', command=self.refresh_devices).grid(sticky='NESW')
            return

        deviceframe = ttk.Frame(self.frame)
        deviceframe.grid(sticky='NESW', pady=10)
        deviceframe.grid_columnconfigure(0, weight = 1)
        self.devicescb = ttk.Combobox(deviceframe, state='readonly', values=[d.name for d in self.devices], postcommand=self.refresh_devices)
        self.devicescb.set(self.device.name)
        self.devicescb.grid(sticky='NESW')
        self.devicescb.bind('<<ComboboxSelected>>', lambda e: self.gui_open_device(self.devicescb.current()))

        open_button = ttk.Button(deviceframe, text='Show video', command=self.open_camera_window)
        open_button.grid(row=0, column=1, sticky='NESW')

        cframe = ttk.Frame(self.frame)
        cframe.grid()

        flat_ctrls = [c for page in self.camera.get_ctrl_pages() for cat in page.categories for c in cat.ctrls]
        for row, c in enumerate(flat_ctrls):
            labelframe = ttk.Frame(cframe)
            labelframe.grid(column=0, row=row, sticky='NW')
            ctrllabel = ttk.Label(labelframe, text=c.name)
            ctrllabel.grid(column=0, row=0, sticky='NW', ipadx=2)

            c.gui_ctrls = [ctrllabel]

            if c.type == 'integer':
                c.uvar = IntVar(cframe, c.value) # for update and label
                c.uvar.trace_add('write', lambda v,a,b,c=c: self.update_ctrl(c, c.uvar.get()))

                # step handling
                c.var = IntVar(cframe, c.value)
                if c.step and c.step != 1:
                    c.var.trace_add('write', lambda v,a,b,c=c: [
                        c.var.get() == c.uvar.get()-1 and c.var.set(c.uvar.get() - c.step), # handle key left
                        c.var.get() == c.uvar.get()+1 and c.var.set(c.uvar.get() + c.step), # handle key right
                        c.var.set(c.var.get() - c.var.get() % c.step
                            if c.var.get() % c.step < c.step/2 else
                            c.var.get() - c.var.get() % c.step + c.step), # handle mouse
                        c.var.get() != c.uvar.get() and c.uvar.set(c.var.get()),
                        c.gui_sc.set(c.var.get()),
                    ])
                else:
                    c.var.trace_add('write', lambda v,a,b,c=c: c.uvar.set(c.var.get()))

                c.gui_sc = ttk.Scale(cframe, style='Highlight.Horizontal.TScale', from_=c.min, to=c.max, variable=c.var, orient='horizontal')
                if c.zeroer:
                    c.gui_sc.bind('<ButtonRelease-1>', lambda e, c=c: c.var.set(0))
                    c.gui_sc.bind('<KeyRelease>', lambda e, c=c: c.var.set(0))
                c.gui_sc.grid(row=row,column=1, sticky='EW', ipadx=2, ipady=2)
                label = ttk.Label(cframe, textvariable=c.uvar, justify='right')
                label.grid(row=row, column=2, sticky='NE', ipadx=4)
                c.gui_ctrls += [c.gui_sc, label]

            elif c.type == 'boolean':
                menuctrls = ttk.Frame(cframe)
                menuctrls.grid(row=row, column=1, sticky='NESW')
                c.var = IntVar(menuctrls, c.value)
                c.var.trace_add('write', lambda v,a,b,c=c: self.update_ctrl(c, c.var.get()))
                ttk.Radiobutton(menuctrls, text='Off', variable=c.var, value=0).grid(row=0, column=0, sticky='NESW', ipadx=10)
                ttk.Radiobutton(menuctrls, text='On', variable=c.var, value=1).grid(row=0, column=1, sticky='NESW', ipadx=10)
                c.gui_ctrls += menuctrls.winfo_children()

            elif c.type == 'button':
                buttonctrls = ttk.Frame(cframe)
                buttonctrls.grid(row=row, column=1, sticky='NESW')
                c.var = StringVar(buttonctrls, c.value)
                c.var.trace_add('write', lambda v,a,b,c=c: self.update_ctrl(c, c.var.get()))
                filtered_menu = [m for m in c.menu if m.value is not None]
                for column, m in enumerate(filtered_menu):
                    ttk.Button(buttonctrls, text=m.name, style='Short.TButton', command=lambda c=c,m=m: c.var.set(m.text_id)).grid(column=column%4, row=column//4, sticky='NESW')
                c.gui_ctrls += buttonctrls.winfo_children()

            elif c.type == 'info':
                c.svar = StringVar(cframe, c.value)
                entry = ttk.Entry(cframe, textvariable=c.svar, justify='right', state='readonly', width=32)
                entry.grid(row=row, column=1, sticky='NESW', ipadx=4)
                c.gui_ctrls += [entry]

            elif c.type == 'menu':
                c.var = StringVar(cframe, c.value)
                c.var.trace_add('write', lambda v,a,b,c=c: self.update_ctrl(c, c.var.get()))
                if len(c.menu) < 4 and not c.menu_dd:
                    menuctrls = ttk.Frame(cframe)
                    menuctrls.grid(row=row, column=1, sticky='NESW')
                    for column, m in enumerate(c.menu):
                        ttk.Radiobutton(menuctrls, text=m.name, variable=c.var, value=m.text_id).grid(column=column, row=0, sticky='NESW', ipadx=10)
                    c.gui_ctrls += menuctrls.winfo_children()
                else:
                    menulabels = [m.text_id for m in c.menu]
                    cb = ttk.Combobox(cframe, state='readonly', exportselection=0, values=menulabels, textvariable=c.var)
                    cb.grid(column=1, row=row, sticky='NESW')
                    c.gui_ctrls += [cb]

            if c.default != None:
                btn = ttk.Button(labelframe, text='«', width=2, style='BorderlessShort.TButton', command=lambda ctrl=c: ctrl.var.set(ctrl.default))
                btn.grid(row=0, column=1, sticky='N')
                c.gui_ctrls += [btn]
                c.gui_default_btn = btn

        self.update_ctrls_state()

    def update_ctrl(self, ctrl, value):
        # only update if out of sync (when new value comes from the gui)
        if ctrl.value != value:
            errs = []
            self.camera.setup_ctrls({ctrl.text_id: value}, errs)
            if errs:
                self.window.after_idle(lambda errs=errs: messagebox.showwarning(message='\n'.join(errs)))
                self.window.after_idle(self.update_ctrl_value, ctrl)

        self.update_ctrls_state()
        if ctrl.reopener:
            self.reopen_device()

    def update_ctrls_state(self):
        for c in self.camera.get_ctrls():
            self.update_ctrl_state(c)

    def update_ctrl_state(self, c):
        for gui_ctrl in c.gui_ctrls:
            state = ['disabled'] if c.inactive else ['!disabled']
            gui_ctrl.state(state)
        self.update_default_btn(c)

    def update_ctrl_value(self, c):
        if c.value is not None:
            c.var.set(c.value)
        self.update_ctrl_state(c)

    def update_default_btn(self, c):
        if c.default != None:
            visible = c.value != None and c.default != c.value or \
                c.get_default != None and not c.get_default()
            if visible:
                c.gui_default_btn.configure(text='«')
            else:
                c.gui_default_btn.configure(text='')
                c.gui_default_btn.state(['disabled', '!focus'])

    def start(self):
        self.window.mainloop()

    def kill_child_processes(self):
        for proc in self.child_processes:
            proc.kill()


if __name__ == '__main__':
    gui = CameraCtrlsGui()
    gui.start()
    gui.kill_child_processes()
