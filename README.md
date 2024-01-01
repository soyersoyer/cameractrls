# cameractrls

<img align='left' height='140' src='https://github.com/soyersoyer/cameractrls/raw/main/pkg/hu.irl.cameractrls.svg'>

Camera controls for Linux

It's a standalone Python CLI and GUI (GTK3, GTK4, TK) and camera Viewer (SDL) to set the camera controls in Linux. It can set the V4L2 controls and it is extendable with the non standard controls. Currently it has a Logitech extension (LED mode, LED frequency, BRIO FoV, Relative Pan/Tilt, PTZ presets), Kiyo Pro extension (HDR, HDR mode, FoV, AF mode, Save), Systemd extension (Save and restore controls with Systemd path+service).

# Install
<a href='https://flathub.org/apps/details/hu.irl.cameractrls'><img width='240' alt='Download on Flathub' src='https://flathub.org/assets/badges/flathub-badge-en.png'/></a>
<a href='https://snapcraft.io/cameractrls'><img height='80' alt='Get it from the Snap Store' src='https://snapcraft.io/static/images/badges/en/snap-store-black.svg'/></a>

On Arch `pacman -S cameractrls`

## Git Install method

Install the dependencies via apt:
```shell
sudo apt install git libsdl2-2.0-0 libturbojpeg
```

or via dnf:
```shell
sudo dnf install git SDL2 turbojpeg
```

Clone the repo
```shell
git clone https://github.com/soyersoyer/cameractrls.git
cd cameractrls
```

# cameractrlsgtk
GTK3 GUI for the Camera controls

<img alt="cameractrls launcher" src="https://github.com/soyersoyer/cameractrls/raw/main/screenshots/gui_launcher.png" width="200">

<div>
<img alt="cameractrls crop screen" src="https://github.com/soyersoyer/cameractrls/raw/main/screenshots/gui_screen_gtk_1.png" width="380">
<img alt="cameractrls image screen" src="https://github.com/soyersoyer/cameractrls/raw/main/screenshots/gui_screen_gtk_2.png" width="380">
<img alt="cameractrls exposure screen" src="https://github.com/soyersoyer/cameractrls/raw/main/screenshots/gui_screen_gtk_3.png" width="380">
<img alt="cameractrls advanced screen" src="https://github.com/soyersoyer/cameractrls/raw/main/screenshots/gui_screen_gtk_4.png" width="380">
<img alt="cameractrls capture screen" src="https://github.com/soyersoyer/cameractrls/raw/main/screenshots/gui_screen_gtk_5.png" width="380">
</div>

### GTK3 GUI install

Add desktop file to the launcher
```shell
desktop-file-install --dir="$HOME/.local/share/applications" \
--set-key=Exec --set-value="$PWD/cameractrlsgtk.py" \
--set-key=Path --set-value="$PWD" \
--set-key=Icon --set-value="$PWD/pkg/hu.irl.cameractrls.svg" \
pkg/hu.irl.cameractrls.desktop
```

Run from the launcher or from the shell
```shell
./cameractrlsgtk.py
```

### GTK4 GUI install (experimental)

Add desktop file to the launcher
```shell
desktop-file-install --dir="$HOME/.local/share/applications" \
--set-key=Exec --set-value="$PWD/cameractrlsgtk4.py" \
--set-key=Path --set-value="$PWD" \
--set-key=Icon --set-value="$PWD/pkg/hu.irl.cameractrls.svg" \
pkg/hu.irl.cameractrls.desktop
```

Run from the launcher or from the shell
```shell
./cameractrlsgtk4.py
```

# cameractrlstk
TKinter GUI for the Camera controls

If you like old looking user interfaces.

<img alt="cameractrls tk screen" src="https://github.com/soyersoyer/cameractrls/raw/main/screenshots/gui_screen_tk.png" width="400">

### TK GUI install

Install the python3 tkinter dependency via apt:
```shell
sudo apt install python3-tk
```

or via dnf:
```shell
sudo dnf install python3-tkinter
```

Add desktop file to the launcher
```shell
desktop-file-install --dir="$HOME/.local/share/applications" \
--set-key=Exec --set-value="$PWD/cameractrlstk.py" \
--set-key=Path --set-value="$PWD" \
--set-key=Icon --set-value="$PWD/pkg/hu.irl.cameractrls.svg" \
pkg/hu.irl.cameractrls.desktop
```

Run from the launcher or from the shell
```shell
./cameractrlstk.py
```

# cameractrls.py

The CLI.

Run the cameractrls
```shell
./cameractrls.py
```
```
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
```
```
usage: ./cameraview.py [--help] [-d DEVICE] [-s SIZE] [-r ANGLE] [-m FLIP] [-c COLORMAP]

optional arguments:
  -h, --help         show this help message and exit
  -d DEVICE          use DEVICE, default /dev/video0
  -s SIZE            put window inside SIZE rectangle (wxh), default unset
  -r ANGLE           rotate the image by ANGLE, default 0
  -m FLIP            mirror the image by FLIP, default no, (no, h, v, hv)
  -c COLORMAP        set colormap, default none
                    (none, grayscale, inferno, viridis, ironblack, rainbow)

example:
  ./cameraview.py -d /dev/video2

shortcuts:
  f: toggle fullscreen
  r: ANGLE +90 (shift+r -90)
  m: FLIP next (shift+m prev)
  c: COLORMAP next (shift+c prev)
```

# Updating the cameractrls

```shell
git pull
```

# Deleting the cameractrls

Disable, stop and delete the systemd paths, services:
```shell
cd ~/.config/systemd/user
systemctl --user disable --now cameractrls-*
rm cameractrls-*
```

Remove launcher shortcut
```shell
rm ~/.local/share/applications/hu.irl.cameractrls.desktop
```

Delete the cameractrls:
```shell
rm -rf cameractrls
```

# Partnership opportunity for vendors

Linux usage is increasing every year, currently around 3-4%.

Due to the low adoption of Linux, Camera control software with custom controls
is usually only available for Windows/MacOS, so Linux users cannot take
advantage of the true potential of each camera.

If you want happy Linux customers and if your camera has custom controls that
are missing from this app, just send me a camera and I'll add them.

Or of course, you can create a PR.
