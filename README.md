# cameractrls
Camera controls for Linux

It's a standalone Python CLI and GUI (GTK3, GTK4, TK) and camera Viewer (SDL) to set the camera controls in Linux. It can set the V4L2 controls and it is extendable with the non standard controls. Currently it has a Logitech extension (LED mode, LED frequency, BRIO FoV, relative Pan/Tilt), Kiyo Pro extension (HDR, HDR mode, FoV, AF mode, Save), Systemd extension (Save and restore controls with Systemd path+service).

# Install
<a href='https://flathub.org/apps/details/hu.irl.cameractrls'><img width='240' alt='Download on Flathub' src='https://flathub.org/assets/badges/flathub-badge-en.png'/></a>
<a href='https://snapcraft.io/cameractrls'><img height='80' alt='Get it from the Snap Store' src='https://snapcraft.io/static/images/badges/en/snap-store-black.svg'/></a>

On Arch `pacman -S cameractrls`

For the git mode read below

# cameractrlsgtk
GTK GUI for the Camera controls

<img alt="cameractrls launcher" src="https://github.com/soyersoyer/cameractrls/raw/main/screenshots/gui_launcher.png" width="200">

<div>
<img alt="cameractrls crop screen" src="https://github.com/soyersoyer/cameractrls/raw/main/screenshots/gui_screen_gtk_1.png" width="380">
<img alt="cameractrls image screen" src="https://github.com/soyersoyer/cameractrls/raw/main/screenshots/gui_screen_gtk_2.png" width="380">
<img alt="cameractrls exposure screen" src="https://github.com/soyersoyer/cameractrls/raw/main/screenshots/gui_screen_gtk_3.png" width="380">
<img alt="cameractrls advanced screen" src="https://github.com/soyersoyer/cameractrls/raw/main/screenshots/gui_screen_gtk_4.png" width="380">
<img alt="cameractrls capture screen" src="https://github.com/soyersoyer/cameractrls/raw/main/screenshots/gui_screen_gtk_5.png" width="380">
</div>

### GTK3 GUI install

Install the dependencies
```shell
sudo apt install libsdl2-2.0-0 libturbojpeg
```

Clone the repo
```shell
git clone https://github.com/soyersoyer/cameractrls.git
```

Add icon and desktop file to the launcher
```shell
cd cameractrls
xdg-icon-resource install --novendor --size 256 pkg/icon.png hu.irl.cameractrls
desktop-file-install --dir="$HOME/.local/share/applications" \
--set-key=Exec --set-value="$PWD/cameractrlsgtk.py" \
--set-key=Path --set-value="$PWD" \
pkg/hu.irl.cameractrls.desktop
```

Run from the launcher or from the shell
```shell
./cameractrlsgtk.py
```

### GTK4 GUI install (experimental)

Install the dependencies
```shell
sudo apt install libsdl2-2.0-0 libturbojpeg
```

Clone the repo
```shell
git clone https://github.com/soyersoyer/cameractrls.git
```

Add icon and desktop file to the launcher
```shell
cd cameractrls
xdg-icon-resource install --novendor --size 256 pkg/icon.png hu.irl.cameractrls
desktop-file-install --dir="$HOME/.local/share/applications" \
--set-key=Exec --set-value="$PWD/cameractrlsgtk4.py" \
--set-key=Path --set-value="$PWD" \
pkg/hu.irl.cameractrls.desktop
```

Run from the launcher or from the shell
```shell
./cameractrlsgtk4.py
```

# cameractrlstk
TKinter GUI for the Camera controls

If you like the old user interfaces.

<img alt="cameractrls launcher" src="https://github.com/soyersoyer/cameractrls/raw/main/screenshots/gui_launcher.png" width="200">

<img alt="cameractrls tk screen" src="https://github.com/soyersoyer/cameractrls/raw/main/screenshots/gui_screen_tk.png" width="400">


### TK GUI install

Install the dependencies
```shell
sudo apt install python3-tk libsdl2-2.0-0 libturbojpeg
```

Clone the repo
```shell
git clone https://github.com/soyersoyer/cameractrls.git
```

Add icon and desktop file to the launcher
```shell
cd cameractrls
xdg-icon-resource install --novendor --size 256 pkg/icon.png hu.irl.cameractrls
desktop-file-install --dir="$HOME/.local/share/applications" \
--set-key=Exec --set-value="$PWD/cameractrlstk.py" \
--set-key=Path --set-value="$PWD" \
pkg/hu.irl.cameractrls.desktop
```

Run from the launcher or from the shell
```shell
./cameractrlstk.py
```

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

# cameraview.py

The camera viewer.

```shell
 ./cameraview.py -h
usage: ./cameraview.py [--help] [-d DEVICE] [-r ANGLE] [-m FLIP]

optional arguments:
  -h, --help         show this help message and exit
  -d DEVICE          use DEVICE, default /dev/video0
  -r ANGLE           rotate the image by ANGLE, default 0
  -m FLIP            mirror the image by FLIP, default no, (no, h, v, hv)

example:
  ./cameraview.py -d /dev/video2

shortcuts:
  f: toggle fullscreen
  r: ANGLE +90 (shift+r -90)
  m: FLIP next (shift+m prev)
```

# Updating the cameractrls

```shell
cd cameractrls
git pull
```

# Deleting the cameractrls

Disable, stop and delete the systemd paths, services:
```shell
cd ~/.config/systemd/user
systemctl --user disable --now cameractrls-*
rm cameractrls-*
```

Remove the icon and launcher shortcut
```shell
xdg-icon-resource uninstall --size 256 hu.irl.cameractrls
rm ~/.local/share/applications/hu.irl.cameractrls.desktop
```

Delete the cameractrls:
```shell
rm -rf cameractrls
```
