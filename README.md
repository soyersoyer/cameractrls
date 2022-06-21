# cameractrls
Camera controls for Linux

It's a standalone Python CLI and GUI (GTK, TK) to set the Camera controls in Linux. It can set the V4L2 controls and it is extendable with the non standard controls. Currently it has a Logitech extension (Led mode, led frequency), Kiyo Pro extension (HDR, HDR mode, FoV, AF mode, Save), Systemd extension (Save and restore controls with Systemd path+service).

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


# cameractrlsgtk
GTK GUI for the Camera controls

![cameractrls launcher](https://github.com/soyersoyer/cameractrls/raw/main/images/gui_launcher.png)

![cameractrls basic screen](https://github.com/soyersoyer/cameractrls/raw/main/images/gui_screen_gtk_1.png)

![cameractrls advanced screen](https://github.com/soyersoyer/cameractrls/raw/main/images/gui_screen_gtk_2.png)

![cameractrls capture screen](https://github.com/soyersoyer/cameractrls/raw/main/images/gui_screen_gtk_3.png)

### GTK GUI install

Clone the repo
```shell
git clone https://github.com/soyersoyer/cameractrls.git
```

Add the desktop file to the launcher
```shell
cd cameractrls
desktop-file-install --dir="$HOME/.local/share/applications" \
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
desktop-file-install --dir="$HOME/.local/share/applications" \
--set-icon="$PWD/images/icon_256.png" \
--set-key=Exec --set-value="$PWD/cameractrlstk.py" \
--set-key=Path --set-value="$PWD" \
cameractrls.desktop
```

Run from the launcher or from the shell
```shell
./cameractrlstk.py
```

### Updating the cameractrls

```shell
cd cameractrls
git pull
```

### Deleting the cameractrls

Disable, stop and delete the systemd paths, service:
```shell
cd ~/.config/systemd/user
systemctl --user disable --now cameractrls-*
rm cameractrls-*
```

Remove the desktop shortcut
```shell
rm ~/.local/share/applications/cameractrls.desktop
```

Delete the cameractrls:
```shell
rm -rf cameractrls
```
