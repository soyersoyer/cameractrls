# Changelog

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
