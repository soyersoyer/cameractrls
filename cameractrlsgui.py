#!/usr/bin/env python3

import os, logging, sys, webbrowser
from cameractrls import CameraCtrls, get_device_capabilities, V4L2_CAP_VIDEO_CAPTURE

try:
    from tkinter import Tk, ttk, PhotoImage, Scale, IntVar, StringVar
except Exception as e:
    logging.error(f'tkinter import failed: {e}, please install the python3-tk package')
    sys.exit(3)

ghurl = 'https://github.com/soyersoyer/cameractrls'
version = 'v0.1.1'

v4ldirs = {
    '/dev/v4l/by-id/': '',
    '/dev/v4l/by-path/': '',
    '/dev/': 'video',
}

def get_devices(dirs):
    devices = []
    resolved_devices = []
    for dir, prefix in dirs.items():
        if not os.path.isdir(dir):
            continue
        for device in os.listdir(dir):
            if not device.startswith(prefix):
                continue
            device = dir + device
            resolved = device if not os.path.islink(device) else os.path.abspath(dir + os.readlink(device))
            if resolved in resolved_devices:
                continue
            devices.append(device)
            resolved_devices.append(resolved)
    devices = [d for d in devices if get_device_capabilities(d) & V4L2_CAP_VIDEO_CAPTURE]
    return devices

class CameraCtrlsGui:
    def __init__(self):
        self.devices = []
        
        self.fd = 0
        self.device = ''
        self.camera = None

        self.window = None
        self.kpsmallimg = None
        self.frame = None
        self.devicescb = None

        self.init_window()
        self.refresh_devices()

    def init_window(self):
        self.window = Tk(className='cameractrls')
        self.kpsmallimg = PhotoImage(file='images/kiyopro_240.png')
        self.window.wm_iconphoto(True, self.kpsmallimg)

        s = ttk.Style()
        s.configure('BorderlessShort.TButton', padding=[10,0,10,0], borderwidth=0)
        
        head = ttk.Frame(self.window)
        head.grid(row=1, sticky='E')

        ttk.Label(head, text=f'cameractrls {version} | ').grid(row=0, column=0)
        gh = ttk.Label(head, text='GitHub★', foreground='blue', cursor='hand2')
        gh.bind('<Button-1>', lambda e: webbrowser.open(ghurl))
        gh.grid(row=0, column=1)

    def refresh_devices(self):
        self.devices = get_devices(v4ldirs)
        if self.device not in self.devices:
            self.close_device()
            if len(self.devices):
                self.open_device(self.devices[0])
            self.init_gui_device()
        if self.devicescb:
            self.devicescb['values'] = self.devices

    def gui_open_device(self, device):
        self.close_device()
        self.open_device(device)
        self.init_gui_device()

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
            self.frame.grid_forget()
            self.frame.destroy()
            self.devicescb = None

        self.frame = ttk.Frame(self.window, padding=10)
        self.frame.grid(row=0)

        if len(self.devices) == 0:
            ttk.Label(self.frame, text='0 camera found', padding=10).grid()
            ttk.Button(self.frame, text='Refresh', command=self.refresh_devices).grid(sticky='NESW')
            return

        self.devicescb = ttk.Combobox(self.frame, state='readonly', values=self.devices, postcommand=self.refresh_devices)
        self.devicescb.set(self.device)
        self.devicescb.grid(sticky='NESW', pady=10)
        self.devicescb.bind('<<ComboboxSelected>>', lambda e: self.gui_open_device(self.devicescb.get()))

        cframe = ttk.Frame(self.frame)
        cframe.grid()

        row = 0
        for c in self.camera.get_ctrls():
            ttk.Label(cframe, text=c.name).grid(column=0, row=row, sticky='NW', ipadx=2)
            column = 1
            
            if c.type == 'integer':
                c.var = IntVar(cframe, c.value)
                c.var.trace_add('write', lambda v,a,b,ctrl=c: self.update_ctrl(ctrl))
                # ttk.Scale doesn't support resolution, using tk.Scale
                sc = Scale(cframe, from_=c.min, to=c.max, resolution=c.step, variable=c.var, showvalue=False, orient='horizontal')
                sc.set(c.value)
                sc.grid(row=row,column=1, sticky='NESW', ipadx=2)
                label = ttk.Label(cframe, textvariable=c.var, justify='right')
                label.grid(row=row, column=2, sticky='NE', ipadx=4)
                
                btn = ttk.Button(cframe, text='⟳', width=1, style='BorderlessShort.TButton', command=lambda ctrl=c: ctrl.var.set(ctrl.default))
                btn.grid(row=row, column=3, sticky='N')
                c.gui_ctrls = [sc, label, btn]

            elif c.type == 'boolean':
                menuctrls = ttk.Frame(cframe)
                menuctrls.grid(row=row, column=1, sticky='NESW')
                c.var = IntVar(menuctrls, c.value)
                c.var.trace_add('write', lambda v,a,b,ctrl=c: self.update_ctrl(ctrl))
                ttk.Radiobutton(menuctrls, text='Off', variable=c.var, value=0).grid(row=0, column=0, sticky='NESW', ipadx=10)
                ttk.Radiobutton(menuctrls, text='On', variable=c.var, value=1).grid(row=0, column=1, sticky='NESW', ipadx=10)
                btn = ttk.Button(cframe, text='⟳', width=1, style='BorderlessShort.TButton', command=lambda ctrl=c: c.var.set(c.default))
                btn.grid(row=row, column=3, sticky='N')
                c.gui_ctrls = menuctrls.winfo_children() + [btn]

            elif c.type == 'menu':
                c.var = StringVar(cframe, c.value)
                c.var.trace_add('write', lambda v,a,b,ctrl=c: self.update_ctrl(ctrl))
                if len(c.menu) < 4:
                    menuctrls = ttk.Frame(cframe)
                    menuctrls.grid(row=row, column=1, sticky='NESW')
                    for m in c.menu:
                        ttk.Radiobutton(menuctrls, text=m.name, variable=c.var, value=m.text_id).grid(column=column, row=0, sticky='NESW', ipadx=10)
                        column += 1
                    c.gui_ctrls = menuctrls.winfo_children()
                else:
                    menulabels = [m.name for m in c.menu]
                    cb = ttk.Combobox(cframe, state='readonly', exportselection=0, values=menulabels)
                    cb.grid(column=1, row=row, sticky='NESW')
                    current = next((m for m in c.menu if m.text_id == c.value), None)
                    if current:
                        cb.set(current.name)
                    cb.bind('<<ComboboxSelected>>', lambda e, c=c, cb=cb: c.var.set(c.menu[cb.current()].text_id))
                    c.gui_ctrls = [cb]

                if c.default != None:
                    btn = ttk.Button(cframe, text='⟳', width=1, style='BorderlessShort.TButton', command=lambda ctrl=c: c.var.set(c.default))
                    btn.grid(row=row, column=3, sticky='N')
                    c.gui_ctrls += [btn]

            row += 1

        self.update_ctrls_state()

    def update_ctrl(self, ctrl):
        self.camera.setup_ctrls({ctrl.text_id: ctrl.var.get()}),
        if ctrl.updater:
            self.camera.update_ctrls()
            self.update_ctrls_state()

    def update_ctrls_state(self):
        for c in self.camera.get_ctrls():
            for gui_ctrl in c.gui_ctrls:
                if hasattr(gui_ctrl, 'state'):
                    state = 'disabled' if c.inactive else '!disabled'
                    gui_ctrl.state([state])
                else:
                    #tk.Scale doesn't support the ttk's .state(), using .configure()
                    state = 'disabled' if c.inactive else 'normal'
                    gui_ctrl.configure(state=state)

    def start(self):
        self.window.mainloop()


if __name__ == '__main__':
    gui = CameraCtrlsGui()
    gui.start()
