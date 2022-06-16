# cameractrls
Camera controls for Linux

It's a standalone Python CLI and GUI (GTK, TK) to set the Camera controls in Linux. It can set the V4L2 controls and it is extendable with the non standard controls. Currently it has a Logitech extension (Led mode, led frequency), Kiyo Pro extension (HDR, HDR mode, FoV, AF mode, Save), Systemd extension (Save).

# cameractrls.py

The CLI.

Clone the repo
```shell
git clone https://github.com/soyersoyer/cameractrls.git
```

Run the cameractrls
```shell
cd cameractrls
./cameractrls.py
usage: ./cameractrls.py [--help] [-d DEVICE] [--list] [-c CONTROLS]

optional arguments:
  -h, --help         show this help message and exit
  -d DEVICE          use DEVICE, default /dev/video0
  -l, --list         list the controls and values
  -L, --list-devices list capture devices
  -c CONTROLS        set CONTROLS (eg.: hdr=on,fov=wide)

example:
  ./cameractrls.py -c brightness=128,kiyo_pro_hdr=on,kiyo_pro_fov=wide
```

```shell
./cameractrls.py --list
Basic / Exposure
 exposure_auto = aperture_priority_mode	( default: aperture_priority_mode values: manual_mode, aperture_priority_mode ) | updater
 exposure_absolute = 156	( default: 156 min: 3 max: 2047 ) | inactive
 exposure_auto_priority = 0	( default: 0 min: 0 max: 1 )
 backlight_compensation = 0	( default: 0 min: 0 max: 1 )
 gain = 0	( default: 0 min: 0 max: 255 )
 kiyo_pro_hdr = None	( values: off, on )
 kiyo_pro_hdr_mode = None	( values: bright, dark )
Basic / Image
 brightness = 128	( default: 128 min: 0 max: 255 )
 contrast = 128	( default: 128 min: 0 max: 255 )
 saturation = 128	( default: 128 min: 0 max: 255 )
 sharpness = 128	( default: 128 min: 0 max: 255 )
Basic / White Balance
 white_balance_temperature_auto = 1	( default: 1 min: 0 max: 1 ) | updater
 white_balance_temperature = 5000	( default: 5000 min: 2000 max: 7500 step: 10 ) | inactive
Advanced / Power Line
 power_line_frequency = 50_hz	( default: 60_hz values: disabled, 50_hz, 60_hz )
Advanced / Pan/Tilt/Zoom/FoV
 pan_absolute = 0	( default: 0 min: -36000 max: 36000 step: 3600 )
 tilt_absolute = 0	( default: 0 min: -36000 max: 36000 step: 3600 )
 zoom_absolute = 100	( default: 100 min: 100 max: 400 )
 kiyo_pro_fov = None	( values: wide, medium, narrow )
Advanced / Focus
 focus_auto = 1	( default: 1 min: 0 max: 1 ) | updater
 focus_absolute = 0	( default: 0 min: 0 max: 600 ) | inactive
 kiyo_pro_af_mode = None	( values: passive, responsive )
Settings / Save
 systemd_save		( buttons: save )
 kiyo_pro_save		( buttons: save )
```


# cameractrlsgtk
GTK GUI for the Camera controls

![cameractrls launcher](https://github.com/soyersoyer/cameractrls/raw/main/images/gui_launcher.png)

![cameractrls screen 1](https://github.com/soyersoyer/cameractrls/raw/main/images/gui_screen_gtk_1.png)

![cameractrls screen 1](https://github.com/soyersoyer/cameractrls/raw/main/images/gui_screen_gtk_2.png)

### GTK GUI install

Clone the repo
```shell
git clone https://github.com/soyersoyer/cameractrls.git
```

Add the desktop file to the launcher
```shell
cd cameractrls
desktop-file-install --dir=$HOME/.local/share/applications \
--set-icon="$PWD/images/icon_256.png" \
--set-key=Exec --set-value="$PWD/cameractrlsgtk.py" \
--set-key=Path --set-value="$PWD" \
cameractrls.desktop
```

Run from the launcher or from the shell
```shell
./cameractrlsgtk.py
```

# cameractrlstk
TKinter GUI for the Camera controls

If you like the old user interfaces.

![cameractrls launcher](https://github.com/soyersoyer/cameractrls/raw/main/images/gui_launcher.png)

![cameractrls tk screen](https://github.com/soyersoyer/cameractrls/raw/main/images/gui_screen_tk.png)


### TK GUI install

Install the tkinter GUI framework
```shell
sudo apt install python3-tk
```

Clone the repo
```shell
git clone https://github.com/soyersoyer/cameractrls.git
```

Add the desktop file to the launcher
```shell
cd cameractrls
desktop-file-install --dir=$HOME/.local/share/applications \
--set-icon="$PWD/images/icon_256.png" \
--set-key=Exec --set-value="$PWD/cameractrlstk.py" \
--set-key=Path --set-value="$PWD" \
cameractrls.desktop
```

Run from the launcher or from the shell
```shell
./cameractrlstk.py
```
