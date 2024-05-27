# Changelog

## [Unreleased]

## [0.6.4] - 2024-05-28

### Fixed
 - Fix config location when XDG_CONFIG_DIR is set (thx Daniel Fox)

## [0.6.3] - 2024-04-11

### Added
 - Added scrollbar to the control panel

### Fixed
 - Cameractrlsd can start even if there is no /dev/v4l directory
 - Preset save writes the config file based on v4l ID

## [0.6.2] - 2024-04-07

### Added
 - Add tooltips to preset controls

### Changed
 - Sort resolutions in descendng order
 - Use only 1 screenshot in metainfo to make the Flatpak image less bloated

## [0.6.1] - 2024-04-03

### Added
 - Set dark mode based on color-scheme
 - Enable DesktopPortal launcer for snap as well

### Changed
 - Check if systemctl enable is successfull
 - Set cameractrlsd loglevel to INFO

## [0.6.0] - 2024-04-01

### Added
 - Control Presets
 - Cameractrlsd, a deamon which restores the controls at device connection
 - Starter for Cameractrlsd with SystemD and DesktopPortal
 - MX Brio FoV support (thx wanderboessenkool)
 - PTZ control keys in cameraview

### Changed
 - use GPLv3 License

### Fixed
 - Various camera opening fixes
 - Better relative MIDI control support
 - Added Zoom Continuous to zeroers to work

### Removed
 - removed cameractrlstk

## [0.5.15] - 2024-02-17

### Fixed
 - Do not use PEP-701 as older pythons do not support it

## [0.5.14] - 2024-02-17

### Added
 - 3DConnexion SpaceMouse support to control PTZ cameras
 - Game Controllers (PS DualSense/Xbox/etc) support to control PTZ cameras
 - MIDI Controllers (MPK Mini or any configurable) support to control PTZ cameras
 - Use Page Up/Page Down for Zoom also (PTZ)
 - Keyboard controls for Absolute PTZ
 - Alt+PresetNum shortcuts for PTZ presets
 - Tooltips for headerbar icons

### Changed
 - Replaced Hamburger menu with About icon

### Fixed
 - Fix Ctrl detection in PTZ controls
 - Eliminating GLib warnings on app closing

## [0.5.13] - 2023-12-22

### Added
 - Logitech PTZ presets
 - Better keyboard control for PTZ
 - Bigger steps for Zoom with Ctrl+Dir, Page Up/Page Down

## [0.5.12] - 2023-12-08

### Added
 - Brio 505 FoV support (thx squiddity)

### Fixed
 - fixed 'list more' button size in the GTK4 app
 - fixed release events of scale widget in the GTK4 app

## [0.5.11] - 2023-10-13

### Fixed
 - Handle invalid menu control value

## [0.5.10] - 2023-08-03

### Added
 - Listen for pixelformat, resolution, FPS changes from other processes
 - Show warnings about invalid FPS values

### Changed
 - Preview calls S_PARM to make uninitialized cameras work

## [0.5.9] - 2023-07-07

### Added
 - V4L2_CID_HDR_SENSOR_MODE, V4L2_CID_IMAGE_[SOURCE|PROC]_CLASS descriptions

### Fixed
 - Shortcuts in cameraview
 - Float FPS handling

### Changed
 - Adjust the window size based on rotation
 - cameraview calls VIDIOC_S_FMT only for Kiyo Pro (it doesn't work without)

## [0.5.8] - 2023-06-26

### Added
 - Colormaps for all pixel formats (some thermal cameras use YUYV for thermal imaging)

## [0.5.7] - 2023-06-24

### Fixed
 - Fixed rotation in preview
 - Clamp percent control values for fewer warnings when using presets

### Changed
 - Use the GTK bundled view-more icon instead of camera-switch

## [0.5.6] - 2023-06-15

### Fixed
 - Fixed ctrl+q quit by closing the camera before

## [0.5.5] - 2023-06-10

### Added
 - Color presets
 - Listen for controls changes from other processes
 - 'default' or percent values can also be set
 - Improved error reporting
 - Exposure time now in µs in the GTK GUIs
 - Exposure time, Gain scales has dark-to-light background

### Changed
 - Removed header buttons border

## [0.5.4] - 2023-05-21

### Changed
 - Limit the initial size of the preview window to control window so it can be placed next to each other

## [0.5.3] - 2023-05-21

### Added
 - Display warnings on the GUIs as well

### Fixed
 - Fixed device listbox margin in GTK app

## [0.5.2] - 2023-05-20

### Added
 - Two more colormaps
 - Capture - Info category with camera informations

### Changed
 - Show devices by name, not by the long v4l path
 - Move device combobox to headerbar
 - Add refresh button to headerbar
 - Limit the size of the preview to fit next to the window
 - Redesigned Zero camera page with snap instructions

## [0.5.1] - 2023-05-17

### Added
 - New Icon (thx Jorge Toledo eldelacajita)
 - Rotate, mirror the preview image
 - Colormaps (inferno, ironblack) for Thermal/ToF camera GREY previews
 - RGB565 format support

### Changed
 - Use edit-undo-symbolic icon instead of ⟳ in default buttons
 - Various GTK/GTK4 fixes
 - Breaking: pkg/icon.png -> pkg/hu.irl.cameractrls.svg

## [0.5.0] - 2023-04-29

### Added
 - Brio 501 FoV support (thx Monkatraz)
 - Colorized White Balance scale
 - GTK4 GUI (experimental)

### Changed
 - Simpler looking scales
 - Icon now comes from the Window Manager
 - Breaking: The desktop filename have to be hu.irl.cameractrls.desktop
 - Breaking: The desktop file moved to pkg dir
 - Breaking: The icon should be installed also

## [0.4.14] - 2023-03-05

### Added
 - Brio 4K Stream Edition FoV support (thx chrishoage)

## [0.4.13] - 2023-03-02

### Added
 - Brio 500 FoV support (thx crabmanX)

## [0.4.12] - 2022-12-04

### Changed
 - Improved error handling and logging
 - The icon has been given some bloom to make it visible even on a dark background (thx nekohayo for the suggestion)

### Fixed
 - Fixed Dynex 1.3MP Webcam preview and fps control (thx dln949 for testing)

## [0.4.11] - 2022-10-19

### Added
 - Pan/Tilt relative and reset controls for some Logitech PTZ cameras (like bcc950)
 - LED and focus controls for some old Logitech cameras (like QuickCam Pro 9000)
 - V4L2 buttons
 - Controls also work with keyboard
 - Pan/Tilt speed controls stop when the key or button released
 - Highlight focused controls in the TK app
 - Gray out the inactive controls
 - Quit with Primary+q
 - New compression page with the Codec and JPEG categories
 - Fullscreen with double-click in the cameraview
 - Support YVYU, UYVY, NV21, YV12, RGB24, BGR24, RX24 formats in the cameraview

### Changed
 - Limit the combobox width in the GTK app
 - Controls fill the width in the GTK app

## [0.4.10] - 2022-10-07

### Added
 - Color Balance category
 - Tooltips for JPEG controls
 - Support cameras with YU12 format
 - Support IR cameras with GREY format

### Changed
 - Advanced/Color Effects moved to Color/Effects
 - Basic/Crop/Privacy moved to Advanced/Privacy
 - Merge Compression page into Advanced page

### Fixed
 - Retain aspect ratio in the cameraview's fullscreen mode

## [0.4.9] - 2022-08-20

### Added
- Control tooltips

### Changed
- Reordered pages

## [0.4.8] - 2022-08-19

### Changed
- Cameractrls, GTK: Crop, Image, Exposure pages for better navigation


## [0.4.7] - 2022-08-19

### Added
- Cameractrls: add Logitech BRIO FoV control

## [0.4.6] - 2022-07-01

### Changed
- Cameraview: use esc to exit
- GTK, TK: close all windows at exit

## [0.4.5] - 2022-06-30

### Added
- AppData for better flatpak integration

## [0.4.4] - 2022-06-29

### Fixed
- SystemdSaver: Don't show systemd save, if it is not available
- GTK: show the open camera button properly
- GTK: suppress warnings or silent exits while changing the capture settings

## [0.4.3] - 2022-06-23

### Fixed
- Fixed systemd saving when systemd user directory doesn't exist
- Fixed cameraview starting, when it's not in the current directory

## [0.4.2] - 2022-06-23

### Added
- Added JPEG support for the cameraview

### Fixed
- Handling cameras that return zero fps

## [0.4.1] - 2022-06-23

### Added
- Added MJPG support for the cameraview

## [0.4.0] - 2022-06-22

### Added
- Ability to view the camera (only in YUYV or NV12 format yet)
- Pixelformat, resolution, fps controls

### Changed
- LogitechCtrls: removed the (not) default values
- SystemdSaver: don't save the inactive controls and save the controls without default values too.
- Adding gamma to Basic.Image

## [0.3.1] - 2022-06-17

### Changed
- TK: better ordering for the controls
- GTK, TK: load the icon from an absolute path (script relative)

## [0.3.0] - 2022-06-16

### Added
- Systemd setting saver, systemd path (inotify watcher) and a systemd service for restoring the controls

### Changed
- TK: move the reset button next to the label
- GTK: place the settings savers in the footer
- CLI: show pages and categories in the list of controls too

## [0.2.3] - 2022-06-11

### Added
- Treat bool like integer V4l2 controls as bool

### Fixed
- String to bool converting in the cameractrls CLI

### Changed
- Added Hue to Basic.Image
- Reorder Gain and Backligh Compensation in Basic.Exposure

## [0.2.2] - 2022-06-10

### Added
- Button control type
- Kiyo Pro save control

### Fixed
- Kiyo Pro controls shouldn't always save on every change

## [0.2.1] - 2022-06-10

### Changed
- New icon

## [0.2.0] - 2022-06-09

### Added
- GTK GUI
- Split controls to pages

## [0.1.2] - 2022-06-08

### Added
- Hide the default buttons when the values are the defaults

## [0.1.1] - 2022-06-07

### Added
- When the menu control is too long using Combobox instead of radiobuttons
- Improved device discovery, added /dev/by-path/\*, /dev/video\*

## [0.1.0] - 2022-06-03

### Added
- CLI script
- V4L2 controls
- Logitech LED controls
- Kiyo Pro controls
- GUI
