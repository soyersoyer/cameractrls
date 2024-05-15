# cameractrls

<img align='left' height='140' src='https://github.com/soyersoyer/cameractrls/raw/main/pkg/hu.irl.cameractrls.svg'>

Camera controls for Linux

It's a standalone Python CLI and GUI (GTK3, GTK4) and camera Viewer (SDL) to set the camera controls in Linux. It can set the V4L2 controls and it is extendable with the non standard controls. Currently it has a Logitech extension (LED mode, LED frequency, BRIO FoV, Relative Pan/Tilt, PTZ presets), Kiyo Pro extension (HDR, HDR mode, FoV, AF mode, Save), Preset extension (Save and restore controls), Control Restore Daemon (to restore presets at device connection).

# Installation

## From Flathub

<a href='https://flathub.org/apps/details/hu.irl.cameractrls'><img width='240' alt='Download on Flathub' src='https://flathub.org/assets/badges/flathub-badge-en.png'/></a>

```
flatpak install flathub hu.irl.cameractrls
```

## From Arch package repository

```
pacman -S cameractrls
```

## From Manjaro package repository

```
pamac install cameractrls
```

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
<img alt="cameractrls PTZ controls" src="https://github.com/soyersoyer/cameractrls/raw/main/screenshots/gui_screen_gtk_6.png" width="380">
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

# cameractrlsd.py

The control restore daemon.

Add it to SystemD/Desktop portal with the GUI/CLI.

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

# PTZ controls

## Keyboard

Control your PTZ camera with the arrow keys/keypad keys/wasd/Home/End/PageUp/PageDown/+/-/Ctrl++/Ctrl+- of your keyboard while one of the PTZ control is in focus or in the cameraview window.

Use Alt+PresetNum to select a preset for logitech_pantilt_preset.

## 3Dconnexion SpaceMouse

Control your camera with your 6DoF [SpaceMouse](https://3dconnexion.com/product/spacemouse-compact/).

```
Z => zoom_absolute
X => pan_absolute
Y => tilt_absolute
RY => pan_speed
RX => tilt_speed
BTN1 => PTZ reset
```

It requires spacenavd and libspnav. (optional, only if you have a SpaceMouse)

```shell
sudo apt install spacenavd libspnav0
sudo cp /usr/share/doc/spacenavd/examples/example-spnavrc /etc/spnavrc
```

or via dnf:
```shell
sudo dnf install spacenavd libspnav
sudo cp /usr/share/doc/spacenavd/example-spnavrc /etc/spnavrc
```

tip: set `led = auto` in /etc/spnavrc

## Game Controllers

Control you camera with your Game Controller ([PS5 DualSense](https://www.playstation.com/accessories/dualsense-wireless-controller/)/[Xbox controller](https://www.xbox.com/accessories/controllers/xbox-wireless-controller)/etc)

```
Left Stick => pan_speed/tilt_speed or pan_absolute/tilt_absolute
Right Stick => pan_absolute/tilt_absolute
DPAD => pan_absolute/tilt_absolute
Left/Right Trigger => zoom_absolute
South/East/West/North/Left Shoulder/Right Shoulder/Back/Start => PTZ Presets 1-8
Guide => PTZ Reset
```

## MIDI Controllers

Control you camera with your MIDI Controller (e.g. [MPK Mini](https://www.akaipro.com/mpk-mini-mk3.html) or any with configurable knobs/joys)

[Configure](https://github.com/tsmetana/mpk3-settings) your MIDI Controller as follows:

```
With joystick:
CC78 => pan_speed/pan_absolute
CC79 => tilt_speed/tilt_absolute

With absolute knobs (knob values: 0-127):
CC71 => pan_absolute
CC72 => tilt_absolute
CC73 => zoom_absolute

With relative knobs (knob values: INC:1 DEC:127):
CC70 => pan_speed
CC74 => tilt_speed
CC75 => pan_absolute
CC76 => tilt_absolute
CC77 => zoom_absolute

CC121 => PTZ reset
PGM0-7 => PTZ presets 1-8
```

# Update cameractrls

```shell
git pull
```

# Update from 0.5.x -> 0.6.x

Disable, stop and delete the old systemd paths, services:
```shell
cd ~/.config/systemd/user
systemctl --user disable --now cameractrls-*
rm cameractrls-*
```

# Delete cameractrls

Disable, stop and delete the systemd service:
```shell
cd ~/.config/systemd/user
systemctl --user disable --now cameractrlsd.service
rm cameractrlsd.service
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
[Contact](mailto:soyer@irl.hu?subject=Partnership)

Or of course, you can create a PR.
