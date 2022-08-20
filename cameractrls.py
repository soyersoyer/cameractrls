#!/usr/bin/env python3

import ctypes, logging, os.path, getopt, sys, subprocess
from fcntl import ioctl

ghurl = 'https://github.com/soyersoyer/cameractrls'
version = 'v0.4.8'


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
    devices.sort()
    return devices

# ioctl

_IOC_NRBITS = 8
_IOC_TYPEBITS = 8
_IOC_SIZEBITS = 14

_IOC_NRSHIFT = 0
_IOC_TYPESHIFT = _IOC_NRSHIFT + _IOC_NRBITS
_IOC_SIZESHIFT = _IOC_TYPESHIFT + _IOC_TYPEBITS
_IOC_DIRSHIFT = _IOC_SIZESHIFT + _IOC_SIZEBITS

_IOC_WRITE = 1
_IOC_READ  = 2

def _IOC(dir_, type_, nr, size):
    return (
        ctypes.c_int32(dir_ << _IOC_DIRSHIFT).value |
        ctypes.c_int32(ord(type_) << _IOC_TYPESHIFT).value |
        ctypes.c_int32(nr << _IOC_NRSHIFT).value |
        ctypes.c_int32(size << _IOC_SIZESHIFT).value)

def _IOC_TYPECHECK(t):
    return ctypes.sizeof(t)

def _IOR(type_, nr, size):
    return _IOC(_IOC_READ, type_, nr, _IOC_TYPECHECK(size))

def _IOW(type_, nr, size):
    return _IOC(_IOC_WRITE, type_, nr, _IOC_TYPECHECK(size))

def _IOWR(type_, nr, size):
    return _IOC(_IOC_READ | _IOC_WRITE, type_, nr, _IOC_TYPECHECK(size))

#
# ioctl structs, codes for UVC extensions
#
enum = ctypes.c_uint

class v4l2_capability(ctypes.Structure):
    _fields_ = [
        ('driver', ctypes.c_char * 16),
        ('card', ctypes.c_char * 32),
        ('bus_info', ctypes.c_char * 32),
        ('version', ctypes.c_uint32),
        ('capabilities', ctypes.c_uint32),
        ('device_caps', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32 * 3),
    ]

# streaming
VIDEO_MAX_PLANES = 8

v4l2_buf_type = enum
(V4L2_BUF_TYPE_VIDEO_CAPTURE) = list(range(1, 2))
v4l2_memory = enum
(V4L2_MEMORY_MMAP) = range(1, 2)
v4l2_field = enum
(V4L2_FIELD_ANY) = range(1)

v4l2_colorspace = enum
(
    V4L2_COLORSPACE_DEFAULT,
    V4L2_COLORSPACE_SMPTE170M,
    V4L2_COLORSPACE_SMPTE240M,
    V4L2_COLORSPACE_REC709,
    V4L2_COLORSPACE_BT878,
    V4L2_COLORSPACE_470_SYSTEM_M,
    V4L2_COLORSPACE_470_SYSTEM_BG,
    V4L2_COLORSPACE_JPEG,
    V4L2_COLORSPACE_SRGB,
    V4L2_COLORSPACE_OPRGB,
    V4L2_COLORSPACE_BT2020,
    V4L2_COLORSPACE_RAW,
    V4L2_COLORSPACE_DCI_P3,
) = range(13)

V4L2_CAP_VIDEO_CAPTURE = 0x00000001
V4L2_CAP_STREAMING = 0x04000000

def v4l2_fourcc(a, b, c, d):
    return ord(a) | (ord(b) << 8) | (ord(c) << 16) | (ord(d) << 24)

V4L2_PIX_FMT_YUYV = v4l2_fourcc('Y', 'U', 'Y', 'V')
V4L2_PIX_FMT_MJPEG = v4l2_fourcc('M', 'J', 'P', 'G')
V4L2_PIX_FMT_JPEG = v4l2_fourcc('J', 'P', 'E', 'G')
V4L2_PIX_FMT_NV12 = v4l2_fourcc('N', 'V', '1', '2')

V4L2_BUF_TYPE_VIDEO_CAPTURE = 1
V4L2_MEMORY_MMAP = 1

class v4l2_fmtdesc(ctypes.Structure):
    _fields_ = [
        ('index', ctypes.c_uint32),
        ('type', ctypes.c_int),
        ('flags', ctypes.c_uint32),
        ('description', ctypes.c_char * 32),
        ('pixelformat', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32 * 4),
    ]

class v4l2_requestbuffers(ctypes.Structure):
    _fields_ = [
        ('count', ctypes.c_uint32),
        ('type', v4l2_buf_type),
        ('memory', v4l2_memory),
        ('reserved', ctypes.c_uint32 * 2),
    ]

class v4l2_plane(ctypes.Structure):
    class _u(ctypes.Union):
        _fields_ = [
            ('mem_offset', ctypes.c_uint32),
            ('userptr', ctypes.c_ulong),
            ('fd', ctypes.c_int32),
        ]
    
    _fields_ = [
        ('bytesused', ctypes.c_uint32),
        ('length', ctypes.c_uint32),
        ('m', _u),
        ('data_offset', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32 * 11),
    ]

class v4l2_pix_format(ctypes.Structure):
    _fields_ = [
        ('width', ctypes.c_uint32),
        ('height', ctypes.c_uint32),
        ('pixelformat', ctypes.c_uint32),
        ('field', v4l2_field),
        ('bytesperline', ctypes.c_uint32),
        ('sizeimage', ctypes.c_uint32),
        ('colorspace', v4l2_colorspace),
        ('priv', ctypes.c_uint32),
    ]

class v4l2_plane_pix_format(ctypes.Structure):
    _fields_ = [
        ('sizeimage', ctypes.c_uint32),
        ('bytesperline', ctypes.c_uint32),
        ('reserved', ctypes.c_uint16 * 6),
    ]
    _pack_ = True


class v4l2_pix_format_mplane(ctypes.Structure):
    class _u(ctypes.Union):
        _fields_ = [
            ('ycbcr_enc', ctypes.c_uint8),
            ('hsv_enc', ctypes.c_uint8),
        ]

    _fields_ = [
        ('width', ctypes.c_uint32),
        ('height', ctypes.c_uint32),
        ('pixelformat', ctypes.c_uint32),
        ('field', v4l2_field),
        ('colorspace', v4l2_colorspace),
        ('plane_fmt', v4l2_plane_pix_format * VIDEO_MAX_PLANES),
        ('num_planes', ctypes.c_uint8),
        ('flags', ctypes.c_uint8),
        ('_u', _u),
        ('quantization', ctypes.c_uint8),
        ('xfer_func', ctypes.c_uint8),
        ('reserved', ctypes.c_uint8 * 7),
    ]

    _anonymous_ = ('_u',)
    _pack_ = True

class v4l2_rect(ctypes.Structure):
    _fields_ = [
        ('left', ctypes.c_int32),
        ('top', ctypes.c_int32),
        ('width', ctypes.c_int32),
        ('height', ctypes.c_int32),
    ]

class v4l2_clip(ctypes.Structure):
    pass
v4l2_clip._fields_ = [
    ('c', v4l2_rect),
    ('next', ctypes.POINTER(v4l2_clip)),
]


class v4l2_vbi_format(ctypes.Structure):
    _fields_ = [
        ('sampling_rate', ctypes.c_uint32),
        ('offset', ctypes.c_uint32),
        ('samples_per_line', ctypes.c_uint32),
        ('sample_format', ctypes.c_uint32),
        ('start', ctypes.c_int32 * 2),
        ('count', ctypes.c_uint32 * 2),
        ('flags', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32 * 2),
    ]

class v4l2_sliced_vbi_format(ctypes.Structure):
    _fields_ = [
        ('service_set', ctypes.c_uint16),
        ('service_lines', ctypes.c_uint16 * 2 * 24),
        ('io_size', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32 * 2),
    ]


class v4l2_window(ctypes.Structure):
    _fields_ = [
        ('w', v4l2_rect),
        ('field', v4l2_field),
        ('chromakey', ctypes.c_uint32),
        ('clips', ctypes.POINTER(v4l2_clip)),
        ('clipcount', ctypes.c_uint32),
        ('bitmap', ctypes.c_void_p),
        ('global_alpha', ctypes.c_uint8),
    ]

class v4l2_format(ctypes.Structure):
    class _u(ctypes.Union):
        _fields_ = [
            ('pix', v4l2_pix_format),
            ('pix_mp', v4l2_pix_format_mplane),
            ('win', v4l2_window),
            ('vbi', v4l2_vbi_format),
            ('sliced', v4l2_sliced_vbi_format),
            ('raw_data', ctypes.c_char * 200),
        ]

    _fields_ = [
        ('type', v4l2_buf_type),
        ('fmt', _u),
    ]

class timeval(ctypes.Structure):
    _fields_ = [
        ('secs', ctypes.c_long),
        ('usecs', ctypes.c_long),
    ]

class v4l2_timecode(ctypes.Structure):
    _fields_ = [
        ('type', ctypes.c_uint32),
        ('flags', ctypes.c_uint32),
        ('frames', ctypes.c_uint8),
        ('seconds', ctypes.c_uint8),
        ('minutes', ctypes.c_uint8),
        ('hours', ctypes.c_uint8),
        ('userbits', ctypes.c_uint8 * 4),
    ]

class v4l2_buffer(ctypes.Structure):
    class _u(ctypes.Union):
        _fields_ = [
            ('offset', ctypes.c_uint32),
            ('userptr', ctypes.c_ulong),
            ('planes', ctypes.POINTER(v4l2_plane)),
            ('fd', ctypes.c_int32),
        ]

    _fields_ = [
        ('index', ctypes.c_uint32),
        ('type', v4l2_buf_type),
        ('bytesused', ctypes.c_uint32),
        ('flags', ctypes.c_uint32),
        ('field', v4l2_field),
        ('timestamp', timeval),
        ('timecode', v4l2_timecode),
        ('sequence', ctypes.c_uint32),
        ('memory', v4l2_memory),
        ('m', _u),
        ('length', ctypes.c_uint32),
        ('input', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32),
    ]

v4l2_frmsizetypes = enum
(
    V4L2_FRMSIZE_TYPE_DISCRETE,
    V4L2_FRMSIZE_TYPE_CONTINUOUS,
    V4L2_FRMSIZE_TYPE_STEPWISE,
) = range(1, 4)


class v4l2_frmsize_discrete(ctypes.Structure):
    _fields_ = [
        ('width', ctypes.c_uint32),
        ('height', ctypes.c_uint32),
    ]


class v4l2_frmsize_stepwise(ctypes.Structure):
    _fields_ = [
        ('min_width', ctypes.c_uint32),
        ('max_width', ctypes.c_uint32),
        ('step_width', ctypes.c_uint32),
        ('min_height', ctypes.c_uint32),
        ('max_height', ctypes.c_uint32),
        ('step_height', ctypes.c_uint32),
    ]


class v4l2_frmsizeenum(ctypes.Structure):
    class _u(ctypes.Union):
        _fields_ = [
            ('discrete', v4l2_frmsize_discrete),
            ('stepwise', v4l2_frmsize_stepwise),
        ]

    _fields_ = [
        ('index', ctypes.c_uint32),
        ('pixel_format', ctypes.c_uint32),
        ('type', ctypes.c_uint32),
        ('_u', _u),
        ('reserved', ctypes.c_uint32 * 2)
    ]

    _anonymous_ = ('_u',)

class v4l2_fract(ctypes.Structure):
    _fields_ = [
        ('numerator', ctypes.c_uint32),
        ('denominator', ctypes.c_uint32),
    ]

v4l2_frmivaltypes = enum
(
    V4L2_FRMIVAL_TYPE_DISCRETE,
    V4L2_FRMIVAL_TYPE_CONTINUOUS,
    V4L2_FRMIVAL_TYPE_STEPWISE,
) = range(1, 4)


class v4l2_frmival_stepwise(ctypes.Structure):
    _fields_ = [
        ('min', v4l2_fract),
        ('max', v4l2_fract),
        ('step', v4l2_fract),
    ]


class v4l2_frmivalenum(ctypes.Structure):
    class _u(ctypes.Union):
        _fields_ = [
            ('discrete', v4l2_fract),
            ('stepwise', v4l2_frmival_stepwise),
        ]

    _fields_ = [
        ('index', ctypes.c_uint32),
        ('pixel_format', ctypes.c_uint32),
        ('width', ctypes.c_uint32),
        ('height', ctypes.c_uint32),
        ('type', ctypes.c_uint32),
        ('_u', _u),
        ('reserved', ctypes.c_uint32 * 2),
    ]

    _anonymous_ = ('_u',)

class v4l2_captureparm(ctypes.Structure):
    _fields_ = [
        ('capability', ctypes.c_uint32),
        ('capturemode', ctypes.c_uint32),
        ('timeperframe', v4l2_fract),
        ('extendedmode', ctypes.c_uint32),
        ('readbuffers', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32 * 4),
    ]


V4L2_MODE_HIGHQUALITY = 0x0001
V4L2_CAP_TIMEPERFRAME = 0x1000

class v4l2_outputparm(ctypes.Structure):
    _fields_ = [
        ('capability', ctypes.c_uint32),
        ('outputmode', ctypes.c_uint32),
        ('timeperframe', v4l2_fract),
        ('extendedmode', ctypes.c_uint32),
        ('writebuffers', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32 * 4),
    ]

class v4l2_streamparm(ctypes.Structure):
    class _u(ctypes.Union):
        _fields_ = [
            ('capture', v4l2_captureparm),
            ('output', v4l2_outputparm),
            ('raw_data', ctypes.c_char * 200),
        ]

    _fields_ = [
        ('type', v4l2_buf_type),
        ('parm', _u)
    ]



VIDIOC_ENUM_FMT = _IOWR('V', 2, v4l2_fmtdesc)
VIDIOC_G_FMT = _IOWR('V', 4, v4l2_format)
VIDIOC_S_FMT = _IOWR('V', 5, v4l2_format)

VIDIOC_REQBUFS = _IOWR('V', 8, v4l2_requestbuffers)
VIDIOC_QUERYBUF	= _IOWR('V', 9, v4l2_buffer)
VIDIOC_QBUF = _IOWR('V', 15, v4l2_buffer)
VIDIOC_DQBUF = _IOWR('V', 17, v4l2_buffer)
VIDIOC_STREAMON = _IOW('V', 18, ctypes.c_int)
VIDIOC_STREAMOFF = _IOW('V', 19, ctypes.c_int)
VIDIOC_G_PARM = _IOWR('V', 21, v4l2_streamparm)
VIDIOC_S_PARM = _IOWR('V', 22, v4l2_streamparm)
VIDIOC_ENUM_FRAMESIZES = _IOWR('V', 74, v4l2_frmsizeenum)
VIDIOC_ENUM_FRAMEINTERVALS = _IOWR('V', 75, v4l2_frmivalenum)

# controls

v4l2_ctrl_type = enum
(
    V4L2_CTRL_TYPE_INTEGER,
    V4L2_CTRL_TYPE_BOOLEAN,
    V4L2_CTRL_TYPE_MENU,
    V4L2_CTRL_TYPE_BUTTON,
    V4L2_CTRL_TYPE_INTEGER64,
    V4L2_CTRL_TYPE_CTRL_CLASS,
    V4L2_CTRL_TYPE_STRING,
    V4L2_CTRL_TYPE_BITMASK,
    V4L2_CTRL_TYPE_INTEGER_MENU,
) = range(1, 10)

V4L2_CTRL_FLAG_UPDATE = 0x0008
V4L2_CTRL_FLAG_INACTIVE = 0x0010
V4L2_CTRL_FLAG_NEXT_CTRL = 0x80000000
V4L2_CTRL_FLAG_NEXT_COMPOUND = 0x40000000

V4L2_CTRL_CLASS_USER = 0x00980000
V4L2_CTRL_CLASS_CAMERA = 0x009a0000

V4L2_CID_BASE = V4L2_CTRL_CLASS_USER | 0x900
V4L2_CID_BRIGHTNESS = V4L2_CID_BASE + 0
V4L2_CID_CONTRAST = V4L2_CID_BASE + 1
V4L2_CID_SATURATION = V4L2_CID_BASE + 2
V4L2_CID_HUE = V4L2_CID_BASE + 3
V4L2_CID_AUTO_WHITE_BALANCE	= V4L2_CID_BASE + 12
V4L2_CID_DO_WHITE_BALANCE = V4L2_CID_BASE + 13
V4L2_CID_RED_BALANCE = V4L2_CID_BASE + 14
V4L2_CID_BLUE_BALANCE = V4L2_CID_BASE + 15
V4L2_CID_GAMMA = V4L2_CID_BASE + 16
V4L2_CID_EXPOSURE = V4L2_CID_BASE + 17
V4L2_CID_AUTOGAIN = V4L2_CID_BASE + 18
V4L2_CID_GAIN = V4L2_CID_BASE + 19
V4L2_CID_HFLIP = V4L2_CID_BASE + 20
V4L2_CID_VFLIP = V4L2_CID_BASE + 21
V4L2_CID_POWER_LINE_FREQUENCY = V4L2_CID_BASE + 24
V4L2_CID_HUE_AUTO = V4L2_CID_BASE + 25
V4L2_CID_WHITE_BALANCE_TEMPERATURE = V4L2_CID_BASE + 26
V4L2_CID_SHARPNESS = V4L2_CID_BASE + 27
V4L2_CID_BACKLIGHT_COMPENSATION = V4L2_CID_BASE + 28
V4L2_CID_CHROMA_AGC = V4L2_CID_BASE + 29
V4L2_CID_COLOR_KILLER = V4L2_CID_BASE + 30
V4L2_CID_COLORFX = V4L2_CID_BASE + 31
V4L2_CID_AUTOBRIGHTNESS = V4L2_CID_BASE + 32
V4L2_CID_BAND_STOP_FILTER = V4L2_CID_BASE + 33
V4L2_CID_ROTATE = V4L2_CID_BASE + 34
V4L2_CID_BG_COLOR = V4L2_CID_BASE + 35
V4L2_CID_CHROMA_GAIN = V4L2_CID_BASE + 36
V4L2_CID_ILLUMINATORS_1 = V4L2_CID_BASE + 37
V4L2_CID_ILLUMINATORS_2 = V4L2_CID_BASE + 38
V4L2_CID_ALPHA_COMPONENT = V4L2_CID_BASE + 41
V4L2_CID_COLORFX_CBCR = V4L2_CID_BASE + 42
V4L2_CID_COLORFX_RGB = V4L2_CID_BASE + 43

V4L2_CID_CAMERA_CLASS_BASE = V4L2_CTRL_CLASS_CAMERA | 0x900
V4L2_CID_EXPOSURE_AUTO = V4L2_CID_CAMERA_CLASS_BASE + 1
V4L2_CID_EXPOSURE_ABSOLUTE = V4L2_CID_CAMERA_CLASS_BASE + 2
V4L2_CID_EXPOSURE_AUTO_PRIORITY = V4L2_CID_CAMERA_CLASS_BASE + 3
V4L2_CID_PAN_RELATIVE = V4L2_CID_CAMERA_CLASS_BASE + 4
V4L2_CID_TILT_RELATIVE = V4L2_CID_CAMERA_CLASS_BASE + 5
V4L2_CID_PAN_RESET = V4L2_CID_CAMERA_CLASS_BASE + 6
V4L2_CID_TILT_RESET = V4L2_CID_CAMERA_CLASS_BASE + 7
V4L2_CID_PAN_ABSOLUTE = V4L2_CID_CAMERA_CLASS_BASE + 8
V4L2_CID_TILT_ABSOLUTE = V4L2_CID_CAMERA_CLASS_BASE + 9
V4L2_CID_FOCUS_ABSOLUTE = V4L2_CID_CAMERA_CLASS_BASE + 10
V4L2_CID_FOCUS_RELATIVE = V4L2_CID_CAMERA_CLASS_BASE + 11
V4L2_CID_FOCUS_AUTO	= V4L2_CID_CAMERA_CLASS_BASE + 12
V4L2_CID_ZOOM_ABSOLUTE = V4L2_CID_CAMERA_CLASS_BASE + 13
V4L2_CID_ZOOM_RELATIVE = V4L2_CID_CAMERA_CLASS_BASE + 14
V4L2_CID_ZOOM_CONTINUOUS = V4L2_CID_CAMERA_CLASS_BASE + 15
V4L2_CID_PRIVACY = V4L2_CID_CAMERA_CLASS_BASE + 16
V4L2_CID_IRIS_ABSOLUTE = V4L2_CID_CAMERA_CLASS_BASE + 17
V4L2_CID_IRIS_RELATIVE = V4L2_CID_CAMERA_CLASS_BASE + 18
V4L2_CID_AUTO_EXPOSURE_BIAS = V4L2_CID_CAMERA_CLASS_BASE + 19
V4L2_CID_AUTO_N_PRESET_WHITE_BALANCE = V4L2_CID_CAMERA_CLASS_BASE + 20
V4L2_CID_WIDE_DYNAMIC_RANGE	= V4L2_CID_CAMERA_CLASS_BASE + 21
V4L2_CID_IMAGE_STABILIZATION = V4L2_CID_CAMERA_CLASS_BASE + 22
V4L2_CID_ISO_SENSITIVITY = V4L2_CID_CAMERA_CLASS_BASE + 23
V4L2_CID_ISO_SENSITIVITY_AUTO = V4L2_CID_CAMERA_CLASS_BASE + 24
V4L2_CID_EXPOSURE_METERING = V4L2_CID_CAMERA_CLASS_BASE + 25
V4L2_CID_SCENE_MODE = V4L2_CID_CAMERA_CLASS_BASE + 26
V4L2_CID_3A_LOCK = V4L2_CID_CAMERA_CLASS_BASE + 27
V4L2_CID_AUTO_FOCUS_START = V4L2_CID_CAMERA_CLASS_BASE + 28
V4L2_CID_AUTO_FOCUS_STOP = V4L2_CID_CAMERA_CLASS_BASE + 29
V4L2_CID_AUTO_FOCUS_STATUS = V4L2_CID_CAMERA_CLASS_BASE + 30
V4L2_CID_AUTO_FOCUS_RANGE = V4L2_CID_CAMERA_CLASS_BASE + 31
V4L2_CID_PAN_SPEED = V4L2_CID_CAMERA_CLASS_BASE + 32
V4L2_CID_TILT_SPEED = V4L2_CID_CAMERA_CLASS_BASE + 33
V4L2_CID_CAMERA_ORIENTATION = V4L2_CID_CAMERA_CLASS_BASE + 34
V4L2_CID_CAMERA_SENSOR_ROTATION = V4L2_CID_CAMERA_CLASS_BASE + 35

V4L2_CTRL_UPDATERS = [
    V4L2_CID_EXPOSURE_AUTO,
    V4L2_CID_FOCUS_AUTO,
    V4L2_CID_AUTO_WHITE_BALANCE,
    V4L2_CID_ISO_SENSITIVITY_AUTO,
]

V4L2_CTRL_REORDERS = {
    V4L2_CID_FOCUS_AUTO: V4L2_CID_FOCUS_ABSOLUTE,
    V4L2_CID_AUTO_WHITE_BALANCE: V4L2_CID_WHITE_BALANCE_TEMPERATURE,
}

V4L2_CTRL_INFO = {
    V4L2_CID_BRIGHTNESS: ('V4L2_CID_BRIGHTNESS', 'Picture brightness, or more precisely, the black level.'),
    V4L2_CID_CONTRAST: ('V4L2_CID_CONTRAST', 'Picture contrast or luma gain.'),
    V4L2_CID_SATURATION: ('V4L2_CID_SATURATION', 'Picture color saturation or chroma gain.'),
    V4L2_CID_HUE: ('V4L2_CID_HUE', 'Hue or color balance.'),
    V4L2_CID_AUTO_WHITE_BALANCE: ('V4L2_CID_AUTO_WHITE_BALANCE', 'Automatic white balance.'),
    V4L2_CID_DO_WHITE_BALANCE: ('V4L2_CID_DO_WHITE_BALANCE', 'This is an action control. When set (the value is ignored), the device will do a white balance and then hold the current setting. Contrast this with the boolean V4L2_CID_AUTO_WHITE_BALANCE, which, when activated, keeps adjusting the white balance.'),
    V4L2_CID_RED_BALANCE: ('V4L2_CID_RED_BALANCE', 'Red chroma balance.'),
    V4L2_CID_BLUE_BALANCE: ('V4L2_CID_BLUE_BALANCE', 'Blue chroma balance.'),
    V4L2_CID_GAMMA: ('V4L2_CID_GAMMA', 'Gamma adjust.'),
    V4L2_CID_EXPOSURE: ('V4L2_CID_EXPOSURE', 'Exposure.'),
    V4L2_CID_AUTOGAIN: ('V4L2_CID_AUTOGAIN', 'Automatic gain/exposure control.'),
    V4L2_CID_GAIN: ('V4L2_CID_GAIN', 'Gain control.'),
    V4L2_CID_HFLIP: ('V4L2_CID_HFLIP', 'Mirror the picture horizontally.'),
    V4L2_CID_VFLIP: ('V4L2_CID_VFLIP', 'Mirror the picture vertically.'),
    V4L2_CID_POWER_LINE_FREQUENCY: ('V4L2_CID_POWER_LINE_FREQUENCY', 'Enables a power line frequency filter to avoid flicker.'),
    V4L2_CID_HUE_AUTO: ('V4L2_CID_HUE_AUTO', 'Enables automatic hue control by the device. The effect of setting V4L2_CID_HUE while automatic hue control is enabled is undefined, drivers should ignore such request.'),
    V4L2_CID_WHITE_BALANCE_TEMPERATURE: ('V4L2_CID_WHITE_BALANCE_TEMPERATURE', 'This control specifies the white balance settings as a color temperature in Kelvin. A driver should have a minimum of 2800 (incandescent) to 6500 (daylight).'),
    V4L2_CID_SHARPNESS: ('V4L2_CID_SHARPNESS', 'Adjusts the sharpness filters in a camera. The minimum value disables the filters, higher values give a sharper picture.'),
    V4L2_CID_BACKLIGHT_COMPENSATION: ('V4L2_CID_BACKLIGHT_COMPENSATION', 'Adjusts the backlight compensation in a camera. The minimum value disables backlight compensation.'),
    V4L2_CID_CHROMA_AGC: ('V4L2_CID_CHROMA_AGC', 'Chroma automatic gain control.'),
    V4L2_CID_CHROMA_GAIN: ('V4L2_CID_CHROMA_GAIN', 'Adjusts the Chroma gain control (for use when chroma AGC is disabled).'),
    V4L2_CID_COLOR_KILLER: ('V4L2_CID_COLOR_KILLER', 'Enable the color killer (i. e. force a black & white image in case of a weak video signal).'),
    V4L2_CID_COLORFX: ('V4L2_CID_COLORFX', 'Selects a color effect.'),
    V4L2_CID_AUTOBRIGHTNESS: ('V4L2_CID_AUTOBRIGHTNESS', 'Enable Automatic Brightness.'),
    V4L2_CID_BAND_STOP_FILTER: ('V4L2_CID_BAND_STOP_FILTER', 'Switch the band-stop filter of a camera sensor on or off, or specify its strength. Such band-stop filters can be used, for example, to filter out the fluorescent light component.'),
    V4L2_CID_ROTATE: ('V4L2_CID_ROTATE', 'Rotates the image by specified angle. Common angles are 90, 270 and 180. Rotating the image to 90 and 270 will reverse the height and width of the display window. It is necessary to set the new height and width of the picture using the VIDIOC_S_FMT ioctl according to the rotation angle selected'),
    V4L2_CID_BG_COLOR: ('V4L2_CID_BG_COLOR', 'Sets the background color on the current output device. Background color needs to be specified in the RGB24 format. The supplied 32 bit value is interpreted as bits 0-7 Red color information, bits 8-15 Green color information, bits 16-23 Blue color information and bits 24-31 must be zero.'),
    V4L2_CID_ILLUMINATORS_1: ('V4L2_CID_ILLUMINATORS_1', 'Switch on or off the illuminator 1 of the device (usually a microscope).'),
    V4L2_CID_ILLUMINATORS_2: ('V4L2_CID_ILLUMINATORS_2', 'Switch on or off the illuminator 2 of the device (usually a microscope).'),
    V4L2_CID_ALPHA_COMPONENT: ('V4L2_CID_ALPHA_COMPONENT', 'Sets the alpha color component. When a capture device (or capture queue of a mem-to-mem device) produces a frame format that includes an alpha component (e.g. packed RGB image formats) and the alpha value is not defined by the device or the mem-to-mem input data this control lets you select the alpha component value of all pixels. When an output device (or output queue of a mem-to-mem device) consumes a frame format that doesn’t include an alpha component and the device supports alpha channel processing this control lets you set the alpha component value of all pixels for further processing in the device.'),
    V4L2_CID_COLORFX_CBCR: ('V4L2_CID_COLORFX_CBCR', 'Determines the Cb and Cr coefficients for V4L2_COLORFX_SET_CBCR color effect. Bits [7:0] of the supplied 32 bit value are interpreted as Cr component, bits [15:8] as Cb component and bits [31:16] must be zero.'),
    V4L2_CID_COLORFX_RGB: ('V4L2_CID_COLORFX_RGB', 'Determines the Red, Green, and Blue coefficients for V4L2_COLORFX_SET_RGB color effect. Bits [7:0] of the supplied 32 bit value are interpreted as Blue component, bits [15:8] as Green component, bits [23:16] as Red component, and bits [31:24] must be zero.'),
    V4L2_CID_EXPOSURE_AUTO: ('V4L2_CID_EXPOSURE_AUTO', 'Enables automatic adjustments of the exposure time and/or iris aperture. The effect of manual changes of the exposure time or iris aperture while these features are enabled is undefined, drivers should ignore such requests. Possible values are: AUTO: Automatic exposure time, automatic iris aperture. MANUAL: Manual exposure time, manual iris. SHUTTER_PRIORITY: Manual exposure time, auto iris. APERTURE_PRIORITY: Auto exposure time, manual iris.'),
    V4L2_CID_EXPOSURE_ABSOLUTE: ('V4L2_CID_EXPOSURE_ABSOLUTE', 'Determines the exposure time of the camera sensor. The exposure time is limited by the frame interval. Drivers should interpret the values as 100 µs units, where the value 1 stands for 1/10000th of a second, 10000 for 1 second and 100000 for 10 seconds.'),
    V4L2_CID_EXPOSURE_AUTO_PRIORITY: ('V4L2_CID_EXPOSURE_AUTO_PRIORITY', 'When V4L2_CID_EXPOSURE_AUTO is set to AUTO or APERTURE_PRIORITY, this control determines if the device may dynamically vary the frame rate. By default this feature is disabled (0) and the frame rate must remain constant.'),
    V4L2_CID_PAN_RELATIVE: ('V4L2_CID_PAN_RELATIVE', 'This control turns the camera horizontally by the specified amount. The unit is undefined. A positive value moves the camera to the right (clockwise when viewed from above), a negative value to the left. A value of zero does not cause motion. This is a write-only control.'),
    V4L2_CID_TILT_RELATIVE: ('V4L2_CID_TILT_RELATIVE', 'This control turns the camera vertically by the specified amount. The unit is undefined. A positive value moves the camera up, a negative value down. A value of zero does not cause motion. This is a write-only control.'),
    V4L2_CID_PAN_RESET: ('V4L2_CID_PAN_RESET', 'When this control is set, the camera moves horizontally to the default position.'),
    V4L2_CID_TILT_RESET: ('V4L2_CID_TILT_RESET', 'When this control is set, the camera moves vertically to the default position.'),
    V4L2_CID_PAN_ABSOLUTE: ('V4L2_CID_PAN_ABSOLUTE', 'This control turns the camera horizontally to the specified position. Positive values move the camera to the right (clockwise when viewed from above), negative values to the left. Drivers should interpret the values as arc seconds, with valid values between -180 * 3600 and +180 * 3600 inclusive.'),
    V4L2_CID_TILT_ABSOLUTE: ('V4L2_CID_TILT_ABSOLUTE', 'This control turns the camera vertically to the specified position. Positive values move the camera up, negative values down. Drivers should interpret the values as arc seconds, with valid values between -180 * 3600 and +180 * 3600 inclusive.'),
    V4L2_CID_FOCUS_ABSOLUTE: ('V4L2_CID_FOCUS_ABSOLUTE', 'This control sets the focal point of the camera to the specified position. The unit is undefined. Positive values set the focus closer to the camera, negative values towards infinity.'),
    V4L2_CID_FOCUS_RELATIVE: ('V4L2_CID_FOCUS_RELATIVE', 'This control moves the focal point of the camera by the specified amount. The unit is undefined. Positive values move the focus closer to the camera, negative values towards infinity. This is a write-only control.'),
    V4L2_CID_FOCUS_AUTO: ('V4L2_CID_FOCUS_AUTO', 'Enables continuous automatic focus adjustments. The effect of manual focus adjustments while this feature is enabled is undefined, drivers should ignore such requests.'),
    V4L2_CID_ZOOM_ABSOLUTE: ('V4L2_CID_ZOOM_ABSOLUTE', 'Specify the objective lens focal length as an absolute value. The zoom unit is driver-specific and its value should be a positive integer.'),
    V4L2_CID_ZOOM_RELATIVE: ('V4L2_CID_ZOOM_RELATIVE', 'Specify the objective lens focal length relatively to the current value. Positive values move the zoom lens group towards the telephoto direction, negative values towards the wide-angle direction. The zoom unit is driver-specific. This is a write-only control.'),
    V4L2_CID_ZOOM_CONTINUOUS: ('V4L2_CID_ZOOM_CONTINUOUS', 'Move the objective lens group at the specified speed until it reaches physical device limits or until an explicit request to stop the movement. A positive value moves the zoom lens group towards the telephoto direction. A value of zero stops the zoom lens group movement. A negative value moves the zoom lens group towards the wide-angle direction. The zoom speed unit is driver-specific.'),
    V4L2_CID_PRIVACY: ('V4L2_CID_PRIVACY', 'Prevent video from being acquired by the camera. When this control is set to TRUE (1), no image can be captured by the camera. Common means to enforce privacy are mechanical obturation of the sensor and firmware image processing, but the device is not restricted to these methods. Devices that implement the privacy control must support read access and may support write access.'),
    V4L2_CID_IRIS_ABSOLUTE: ('V4L2_CID_IRIS_ABSOLUTE', 'This control sets the camera’s aperture to the specified value. The unit is undefined. Larger values open the iris wider, smaller values close it.'),
    V4L2_CID_IRIS_RELATIVE: ('V4L2_CID_IRIS_RELATIVE', 'This control modifies the camera’s aperture by the specified amount. The unit is undefined. Positive values open the iris one step further, negative values close it one step further. This is a write-only control.'),
    V4L2_CID_AUTO_EXPOSURE_BIAS: ('V4L2_CID_AUTO_EXPOSURE_BIAS', 'Determines the automatic exposure compensation, it is effective only when V4L2_CID_EXPOSURE_AUTO control is set to AUTO, SHUTTER_PRIORITY or APERTURE_PRIORITY. It is expressed in terms of EV, drivers should interpret the values as 0.001 EV units, where the value 1000 stands for +1 EV. Increasing the exposure compensation value is equivalent to decreasing the exposure value (EV) and will increase the amount of light at the image sensor. The camera performs the exposure compensation by adjusting absolute exposure time and/or aperture.'),
    V4L2_CID_AUTO_N_PRESET_WHITE_BALANCE: ('V4L2_CID_AUTO_N_PRESET_WHITE_BALANCE', 'Sets white balance to automatic, manual or a preset. The presets determine color temperature of the light as a hint to the camera for white balance adjustments resulting in most accurate color representation. The following white balance presets are listed in order of increasing color temperature.'),
    V4L2_CID_WIDE_DYNAMIC_RANGE: ('V4L2_CID_WIDE_DYNAMIC_RANGE', 'Enables or disables the camera’s wide dynamic range feature. This feature allows to obtain clear images in situations where intensity of the illumination varies significantly throughout the scene, i.e. there are simultaneously very dark and very bright areas. It is most commonly realized in cameras by combining two subsequent frames with different exposure times.'),
    V4L2_CID_IMAGE_STABILIZATION: ('V4L2_CID_IMAGE_STABILIZATION', 'Enables or disables image stabilization.'),
    V4L2_CID_ISO_SENSITIVITY: ('V4L2_CID_ISO_SENSITIVITY', 'Determines ISO equivalent of an image sensor indicating the sensor’s sensitivity to light. The numbers are expressed in arithmetic scale, as per ISO 12232:2006 standard, where doubling the sensor sensitivity is represented by doubling the numerical ISO value. Applications should interpret the values as standard ISO values multiplied by 1000, e.g. control value 800 stands for ISO 0.8. Drivers will usually support only a subset of standard ISO values. The effect of setting this control while the V4L2_CID_ISO_SENSITIVITY_AUTO control is set to a value other than V4L2_CID_ISO_SENSITIVITY_MANUAL is undefined, drivers should ignore such requests.'),
    V4L2_CID_ISO_SENSITIVITY_AUTO: ('V4L2_CID_ISO_SENSITIVITY_AUTO', 'Enables or disables automatic ISO sensitivity adjustments.'),
    V4L2_CID_EXPOSURE_METERING: ('V4L2_CID_EXPOSURE_METERING', 'Determines how the camera measures the amount of light available for the frame exposure. Possible values are:'),
    V4L2_CID_SCENE_MODE: ('V4L2_CID_SCENE_MODE', 'This control allows to select scene programs as the camera automatic modes optimized for common shooting scenes. Within these modes the camera determines best exposure, aperture, focusing, light metering, white balance and equivalent sensitivity. The controls of those parameters are influenced by the scene mode control. An exact behavior in each mode is subject to the camera specification. When the scene mode feature is not used, this control should be set to V4L2_SCENE_MODE_NONE to make sure the other possibly related controls are accessible.'),
    V4L2_CID_3A_LOCK: ('V4L2_CID_3A_LOCK', 'This control locks or unlocks the automatic focus, exposure and white balance. The automatic adjustments can be paused independently by setting the corresponding lock bit to 1. The camera then retains the settings until the lock bit is cleared. The following lock bits are defined: When a given algorithm is not enabled, drivers should ignore requests to lock it and should return no error. An example might be an application setting bit V4L2_LOCK_WHITE_BALANCE when the V4L2_CID_AUTO_WHITE_BALANCE control is set to FALSE. The value of this control may be changed by exposure, white balance or focus controls'),
    V4L2_CID_AUTO_FOCUS_START: ('V4L2_CID_AUTO_FOCUS_START', 'Starts single auto focus process. The effect of setting this control when V4L2_CID_FOCUS_AUTO is set to TRUE (1) is undefined, drivers should ignore such requests.'),
    V4L2_CID_AUTO_FOCUS_STOP: ('V4L2_CID_AUTO_FOCUS_STOP', 'Aborts automatic focusing started with V4L2_CID_AUTO_FOCUS_START control. It is effective only when the continuous autofocus is disabled, that is when V4L2_CID_FOCUS_AUTO control is set to FALSE (0)'),
    V4L2_CID_AUTO_FOCUS_STATUS: ('V4L2_CID_AUTO_FOCUS_STATUS', 'The automatic focus status. This is a read-only control.'),
    V4L2_CID_AUTO_FOCUS_RANGE: ('V4L2_CID_AUTO_FOCUS_RANGE', 'Determines auto focus distance range for which lens may be adjusted.'),
    V4L2_CID_PAN_SPEED: ('V4L2_CID_PAN_SPEED', 'This control turns the camera horizontally at the specific speed. The unit is undefined. A positive value moves the camera to the right (clockwise when viewed from above), a negative value to the left. A value of zero stops the motion if one is in progress and has no effect otherwise.'),
    V4L2_CID_TILT_SPEED: ('V4L2_CID_TILT_SPEED', 'This control turns the camera vertically at the specified speed. The unit is undefined. A positive value moves the camera up, a negative value down. A value of zero stops the motion if one is in progress and has no effect otherwise.'),
    V4L2_CID_CAMERA_ORIENTATION: ('V4L2_CID_CAMERA_ORIENTATION', 'his read-only control describes the camera orientation by reporting its mounting position on the device where the camera is installed. The control value is constant and not modifiable by software. This control is particularly meaningful for devices which have a well defined orientation, such as phones, laptops and portable devices since the control is expressed as a position relative to the device’s intended usage orientation. For example, a camera installed on the user-facing side of a phone, a tablet or a laptop device is said to be have V4L2_CAMERA_ORIENTATION_FRONT orientation, while a camera installed on the opposite side of the front one is said to be have V4L2_CAMERA_ORIENTATION_BACK orientation. Camera sensors not directly attached to the device, or attached in a way that allows them to move freely, such as webcams and digital cameras, are said to have the V4L2_CAMERA_ORIENTATION_EXTERNAL orientation.'),
    V4L2_CID_CAMERA_SENSOR_ROTATION: ('V4L2_CID_CAMERA_SENSOR_ROTATION', 'This read-only control describes the rotation correction in degrees in the counter-clockwise direction to be applied to the captured images once captured to memory to compensate for the camera sensor mounting rotation.'),
}

class v4l2_control(ctypes.Structure):
    _fields_ = [
        ('id', ctypes.c_uint32),
        ('value', ctypes.c_int32),
    ]

class v4l2_queryctrl(ctypes.Structure):
    _fields_ = [
        ('id', ctypes.c_uint32),
        ('type', v4l2_ctrl_type),
        ('name', ctypes.c_char * 32),
        ('minimum', ctypes.c_int32),
        ('maximum', ctypes.c_int32),
        ('step', ctypes.c_int32),
        ('default', ctypes.c_int32),
        ('flags', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32 * 2),
    ]

class v4l2_querymenu(ctypes.Structure):
    class _u(ctypes.Union):
        _fields_ = [
            ('name', ctypes.c_char * 32),
            ('value', ctypes.c_int64),
        ]

    _fields_ = [
        ('id', ctypes.c_uint32),
        ('index', ctypes.c_uint32),
        ('_u', _u),
        ('reserved', ctypes.c_uint32),
    ]
    _anonymous_ = ('_u',)
    _pack_ = True

class uvc_xu_control_query(ctypes.Structure):
    _fields_ = [
        ('unit', ctypes.c_uint8),
        ('selector', ctypes.c_uint8),
        ('query', ctypes.c_uint8),      # Video Class-Specific Request Code,
                                        # defined in linux/usb/video.h A.8.
        ('size', ctypes.c_uint16),
        ('data', ctypes.c_void_p),
    ]

VIDIOC_QUERYCAP = _IOR('V', 0, v4l2_capability)
UVCIOC_CTRL_QUERY = _IOWR('u', 0x21, uvc_xu_control_query)
VIDIOC_G_CTRL = _IOWR('V', 27, v4l2_control)
VIDIOC_S_CTRL = _IOWR('V', 28, v4l2_control)
VIDIOC_QUERYCTRL = _IOWR('V', 36, v4l2_queryctrl)
VIDIOC_QUERYMENU = _IOWR('V', 37, v4l2_querymenu)

# A.8. Video Class-Specific Request Codes
UVC_RC_UNDEFINED = 0x00
UVC_SET_CUR      = 0x01
UVC_GET_CUR      = 0x81
UVC_GET_MIN      = 0x82
UVC_GET_MAX      = 0x83
UVC_GET_RES      = 0x84
UVC_GET_LEN      = 0x85
UVC_GET_INFO     = 0x86
UVC_GET_DEF      = 0x87

EU1_SET_ISP = 0x01
EU1_GET_ISP_RESULT = 0x02

# UVC EU1 extension GUID 23e49ed0-1178-4f31-ae52-d2fb8a8d3b48
UVC_EU1_GUID = b'\xd0\x9e\xe4\x23\x78\x11\x31\x4f\xae\x52\xd2\xfb\x8a\x8d\x3b\x48'

# Razer Kiyo Pro specific registers and values

AF_RESPONSIVE = b'\xff\x06\x00\x00\x00\x00\x00\x00'
AF_PASSIVE =    b'\xff\x06\x01\x00\x00\x00\x00\x00'

HDR_OFF =       b'\xff\x02\x00\x00\x00\x00\x00\x00'
HDR_ON =        b'\xff\x02\x01\x00\x00\x00\x00\x00'

HDR_DARK =      b'\xff\x07\x00\x00\x00\x00\x00\x00'
HDR_BRIGHT =    b'\xff\x07\x01\x00\x00\x00\x00\x00'

FOV_WIDE =       b'\xff\x01\x00\x03\x00\x00\x00\x00'
FOV_MEDIUM_PRE = b'\xff\x01\x00\x03\x01\x00\x00\x00'
FOV_MEDIUM =     b'\xff\x01\x01\x03\x01\x00\x00\x00'
FOV_NARROW_PRE = b'\xff\x01\x00\x03\x02\x00\x00\x00'
FOV_NARROW =     b'\xff\x01\x01\x03\x02\x00\x00\x00'

# Unknown yet, the synapse sends it in start
UNKNOWN =       b'\xff\x04\x00\x00\x00\x00\x00\x00'

# save previous values to the camera
SAVE =          b'\xc0\x03\xa8\x00\x00\x00\x00\x00'

LOAD =          b'\x00\x00\x00\x00\x00\x00\x00\x00'

def to_buf(b):
    return ctypes.create_string_buffer(b)

def get_length_xu_control(fd, unit_id, selector):
    length = ctypes.c_uint16(0)

    xu_ctrl_query = uvc_xu_control_query()
    xu_ctrl_query.unit = unit_id
    xu_ctrl_query.selector = selector
    xu_ctrl_query.query = UVC_GET_LEN
    xu_ctrl_query.size = 2 # sizeof(length)
    xu_ctrl_query.data = ctypes.cast(ctypes.pointer(length), ctypes.c_void_p)

    try:
       ioctl(fd, UVCIOC_CTRL_QUERY, xu_ctrl_query)
    except Exception as e:
        logging.warning(f'UVCIOC_CTRL_QUERY (GET_LEN) - Fd: {fd} - Error: {e}')

    return length

def query_xu_control(fd, unit_id, selector, query, data):
    len = get_length_xu_control(fd, unit_id, selector)

    xu_ctrl_query = uvc_xu_control_query()
    xu_ctrl_query.unit = unit_id
    xu_ctrl_query.selector = selector
    xu_ctrl_query.query = query
    xu_ctrl_query.size = len
    xu_ctrl_query.data = ctypes.cast(ctypes.pointer(data), ctypes.c_void_p)

    try:
        ioctl(fd, UVCIOC_CTRL_QUERY, xu_ctrl_query)
    except Exception as e:
        logging.warning(f'UVCIOC_CTRL_QUERY ({query}) - Fd: {fd} - Error: {e}')

# the usb device descriptors file contains the descriptors in a binary format
# the byte before the extension guid is the extension unit id
def find_unit_id_in_sysfs(device, guid):
    if os.path.islink(device):
        device = os.readlink(device)
    device = os.path.basename(device)
    descfile = f'/sys/class/video4linux/{device}/../../../descriptors'
    if not os.path.isfile(descfile):
        return 0

    try:
        with open(descfile, 'rb') as f:
            descriptors = f.read()
            guid_start = descriptors.find(guid)
            if guid_start > 0:
                return descriptors[guid_start - 1]
    except Exception as e:
        logging.warning(f'Failed to read uvc xu unit id from {descfile}: {e}')

    return 0

def find_usb_ids_in_sysfs(device):
    if os.path.islink(device):
        device = os.readlink(device)
    device = os.path.basename(device)
    vendorfile = f'/sys/class/video4linux/{device}/../../../idVendor'
    productfile = f'/sys/class/video4linux/{device}/../../../idProduct'
    if not os.path.isfile(vendorfile) or not os.path.isfile(productfile):
        return ''

    vendor = read_usb_id_from_file(vendorfile)
    product = read_usb_id_from_file(productfile)

    return vendor + ':' + product

def read_usb_id_from_file(file):
    id = ''
    try:
        with open(file, 'r') as f:
            id = f.read().strip()
    except Exception as e:
        logging.warning(f'Failed to read usb id from {file}: {e}')
    return id

def get_device_capabilities(device):
    cap = v4l2_capability()
    try:
        fd = os.open(device, os.O_RDWR, 0)
        ioctl(fd, VIDIOC_QUERYCAP, cap)
        os.close(fd)
    except Exception as e:
        logging.error(f'get_device_capabilities({device}) failed: {e}')

    return cap.device_caps

def find_by_value(menu, value):
    for m in menu:
        if m.value == value:
            return m
    return None

def find_by_text_id(ctrls, text_id):
    for c in ctrls:
        if c.text_id == text_id:
            return c
    return None

def find_idx(ctrls, pred):
    for i, c in enumerate(ctrls):
        if pred(c):
            return i
    return None

def pop_list_by_text_ids(ctrls, text_ids):
    ret = []
    for text_id in text_ids:
        while True:
            idx = find_idx(ctrls, lambda c: c.text_id.startswith(text_id))
            if idx != None:
                ret.append(ctrls.pop(idx))
            else:
                break
    return ret

def to_bool(val):
    if type(val) == str:
        val = val.lower()
        if val in ('y', 'yes', 't', 'true', 'on', '1'):
            return True
        return False
    return bool(val)


class BaseCtrl:
    def __init__(self, text_id, name, type, value = None, default = None, min = None, max = None, step = None,
                inactive = False, updater = False, reopener = False, menu_dd = False, menu = None, tooltip = None, kernel_id = None):
        self.text_id = text_id
        self.kernel_id = kernel_id
        self.name = name
        self.type = type
        self.value = value
        self.default = default
        self.min = min
        self.max = max
        self.step = step
        self.inactive = inactive
        self.updater = updater
        self.reopener = reopener
        self.menu_dd = menu_dd
        self.menu = menu
        self.tooltip = tooltip

class BaseCtrlMenu:
    def __init__(self, text_id, name, value):
        self.text_id = text_id
        self.name = name
        self.value = value

class KiyoCtrl(BaseCtrl):
    def __init__(self, text_id, name, type, tooltip, menu, ):
        super().__init__(text_id, name, type, tooltip=tooltip, menu=menu)

class KiyoMenu(BaseCtrlMenu):
    def __init__(self, text_id, name, value, before = None):
        super().__init__(text_id, name, value)
        self._before = before

class KiyoProCtrls:
    KIYO_PRO_USB_ID = '1532:0e05'
    def __init__(self, device, fd):
        self.device = device
        self.fd = fd
        self.unit_id = find_unit_id_in_sysfs(device, UVC_EU1_GUID)
        self.usb_ids = find_usb_ids_in_sysfs(device)
        self.get_device_controls()

    def supported(self):
        return self.unit_id != 0 and self.usb_ids == KiyoProCtrls.KIYO_PRO_USB_ID

    def get_device_controls(self):
        if not self.supported():
            self.ctrls = []
            return

        self.ctrls = [
            KiyoCtrl(
                'kiyo_pro_af_mode',
                'AF Mode',
                'menu',
                'Kiyo Pro Auto Focus mode',
                [
                    KiyoMenu('passive', 'Passive', AF_PASSIVE),
                    KiyoMenu('responsive', 'Responsive', AF_RESPONSIVE),
                ]
            ),
            KiyoCtrl(
                'kiyo_pro_hdr',
                'HDR',
                'menu',
                'Kiyo Pro High Dynamic Range',
                [
                    KiyoMenu('off', 'Off', HDR_OFF),
                    KiyoMenu('on', 'On', HDR_ON),
                ]
            ),
            KiyoCtrl(
                'kiyo_pro_hdr_mode',
                'HDR Mode',
                'menu',
                'Kiyo Pro High Dynamic Range mode',
                [
                    KiyoMenu('bright', 'Bright', HDR_BRIGHT),
                    KiyoMenu('dark', 'Dark', HDR_DARK),
                ]
            ),
            KiyoCtrl(
                'kiyo_pro_fov',
                'FoV',
                'menu',
                'Kiyo Pro Field of View',
                [
                    KiyoMenu('narrow', 'Narrow', FOV_NARROW, FOV_NARROW_PRE),
                    KiyoMenu('medium', 'Medium', FOV_MEDIUM, FOV_MEDIUM_PRE),
                    KiyoMenu('wide', 'Wide', FOV_WIDE),
                ]
            ),
            KiyoCtrl(
                'kiyo_pro_save',
                'Save settings to Kiyo Pro',
                'button',
                'Save the settings into he Kiyo Pro\'s NVRAM',
                [
                    KiyoMenu('save', 'Save', SAVE),
                ]
            ),
        ]

    def setup_ctrls(self, params):
        if not self.supported():
            return

        for k, v in params.items():
            ctrl = find_by_text_id(self.ctrls, k)
            if ctrl == None:
                continue
            menu = find_by_text_id(ctrl.menu, v)
            if menu == None:
                logging.warning(f'KiyoProCtrls: can\'t find {v} in {[c.text_id for c in ctrl.menu]}')
                continue
            ctrl.value = menu.text_id

            if menu._before:
                query_xu_control(self.fd, self.unit_id, EU1_SET_ISP, UVC_SET_CUR, to_buf(menu._before))

            query_xu_control(self.fd, self.unit_id, EU1_SET_ISP, UVC_SET_CUR, to_buf(menu.value))


    def update_ctrls(self):
        return

    def get_ctrls(self):
        return self.ctrls

# Logitech peripheral GUID ffe52d21-8030-4e2c-82d9-f587d00540bd
LOGITECH_PERIPHERAL_GUID = b'\x21\x2d\xe5\xff\x30\x80\x2c\x4e\x82\xd9\xf5\x87\xd0\x05\x40\xbd'

LOGITECH_PERIPHERAL_LED1_SEL = 0x09
LOGITECH_PERIPHERAL_LED1_LEN = 5

LOGITECH_PERIPHERAL_LED1_MODE_OFFSET = 1
LOGITECH_PERIPHERAL_LED1_MODE_OFF =   0x00
LOGITECH_PERIPHERAL_LED1_MODE_ON =    0x01
LOGITECH_PERIPHERAL_LED1_MODE_BLINK = 0x02
LOGITECH_PERIPHERAL_LED1_MODE_AUTO =  0x03

LOGITECH_PERIPHERAL_LED1_FREQUENCY_OFFSET = 3

class LogitechCtrl(BaseCtrl):
    def __init__(self, text_id, name, type, tooltip, selector, len, offset, menu = None):
        super().__init__(text_id, name, type, tooltip=tooltip, menu=menu)
        self._selector = selector
        self._len = len
        self._offset = offset

class LogitechCtrls:
    def __init__(self, device, fd):
        self.device = device
        self.fd = fd
        self.unit_id = find_unit_id_in_sysfs(device, LOGITECH_PERIPHERAL_GUID)

        self.get_device_controls()

    def supported(self):
        return self.unit_id != 0

    def get_device_controls(self):
        if not self.supported():
            self.ctrls = []
            return

        self.ctrls = [
            LogitechCtrl(
                'logitech_led1_mode',
                'LED1 Mode',
                'menu',
                'Logitech LED mode',
                LOGITECH_PERIPHERAL_LED1_SEL,
                LOGITECH_PERIPHERAL_LED1_LEN,
                LOGITECH_PERIPHERAL_LED1_MODE_OFFSET,
                [
                    BaseCtrlMenu('off', 'Off', LOGITECH_PERIPHERAL_LED1_MODE_OFF),
                    BaseCtrlMenu('on', 'On', LOGITECH_PERIPHERAL_LED1_MODE_ON),
                    BaseCtrlMenu('blink', 'Blink', LOGITECH_PERIPHERAL_LED1_MODE_BLINK),
                    BaseCtrlMenu('auto', 'Auto', LOGITECH_PERIPHERAL_LED1_MODE_AUTO),
                ]
            ),
            LogitechCtrl(
                'logitech_led1_frequency',
                'LED1 Frequency',
                'integer',
                'Logitech LED frequency',
                LOGITECH_PERIPHERAL_LED1_SEL,
                LOGITECH_PERIPHERAL_LED1_LEN,
                LOGITECH_PERIPHERAL_LED1_FREQUENCY_OFFSET,
            ),
        ]

        for c in self.ctrls:
            minimum_config = to_buf(bytes(c._len))
            maximum_config = to_buf(bytes(c._len))
            current_config = to_buf(bytes(c._len))

            query_xu_control(self.fd, self.unit_id, c._selector, UVC_GET_MIN, minimum_config)
            query_xu_control(self.fd, self.unit_id, c._selector, UVC_GET_MAX, maximum_config)
            query_xu_control(self.fd, self.unit_id, c._selector, UVC_GET_CUR, current_config)

            c.min = minimum_config[c._offset][0]
            c.max = maximum_config[c._offset][0]
            c.value = current_config[c._offset][0]

            if c.type == 'menu':
                valmenu = find_by_value(c.menu, c.value)
                if valmenu:
                    c.value = valmenu.text_id


    def setup_ctrls(self, params):
        if not self.supported():
            return

        for k, v in params.items():
            ctrl = find_by_text_id(self.ctrls, k)
            if ctrl == None:
                continue
            if ctrl.type == 'menu':
                menu  = find_by_text_id(ctrl.menu, v)
                if menu == None:
                    logging.warning(f'LogitechCtrls: can\'t find {v} in {[c.text_id for c in ctrl.menu]}')
                    continue
                desired = menu.value
            elif ctrl.type == 'integer':
                desired = int(v)
            else:
                logging.warning(f'Can\'t set {k} to {v} (Unsupported control type {ctrl.type})')
                continue

            current_config = to_buf(bytes(ctrl._len))
            query_xu_control(self.fd, self.unit_id, ctrl._selector, UVC_GET_CUR, current_config)
            current_config[ctrl._offset] = desired
            query_xu_control(self.fd, self.unit_id, ctrl._selector, UVC_SET_CUR, current_config)
            query_xu_control(self.fd, self.unit_id, ctrl._selector, UVC_GET_CUR, current_config)
            current = current_config[ctrl._offset][0]

            if ctrl.type == 'menu':
                desmenu = find_by_value(ctrl.menu, desired)
                if desmenu:
                    desired = desmenu.text_id
                curmenu = find_by_value(ctrl.menu, current)
                if curmenu:
                    current = curmenu.text_id
            if current != desired:
                logging.warning(f'LogitechCtrls: failed to set {k} to {desired}, current value {current}\n')
                continue

            ctrl.value = desired

    def update_ctrls(self):
        return

    def get_ctrls(self):
        return self.ctrls

# Logitech BRIO GUID 49e40215-f434-47fe-b158-0e885023e51b
LOGITECH_BRIO_GUID = b'\x15\x02\xe4\x49\x34\xf4\xfe\x47\xb1\x58\x0e\x88\x50\x23\xe5\x1b'

LOGITECH_BRIO_FOV_SEL = 0x05
LOGITECH_BRIO_FOV_LEN = 1
LOGITECH_BRIO_FOV_OFFSET = 0

LOGITECH_BRIO_FOV_65 = 0x02
LOGITECH_BRIO_FOV_78 = 0x01
LOGITECH_BRIO_FOV_90 = 0x00


class LogitechBRIOCtrls:
    BRIO_USB_ID = '046d:085e'
    def __init__(self, device, fd):
        self.device = device
        self.fd = fd
        self.unit_id = find_unit_id_in_sysfs(device, LOGITECH_BRIO_GUID)
        self.usb_ids = find_usb_ids_in_sysfs(device)

        self.get_device_controls()

    def supported(self):
        return self.unit_id != 0 and self.usb_ids == LogitechBRIOCtrls.BRIO_USB_ID

    def get_device_controls(self):
        if not self.supported():
            self.ctrls = []
            return

        self.ctrls = [
            LogitechCtrl(
                'logitech_brio_fov',
                'FoV',
                'menu',
                'Logitech BRIO Field of View',
                LOGITECH_BRIO_FOV_SEL,
                LOGITECH_BRIO_FOV_LEN,
                LOGITECH_BRIO_FOV_OFFSET,
                [
                    BaseCtrlMenu('65', '65°', LOGITECH_BRIO_FOV_65),
                    BaseCtrlMenu('78', '78°', LOGITECH_BRIO_FOV_78),
                    BaseCtrlMenu('90', '90°', LOGITECH_BRIO_FOV_90),
                ]
            ),
        ]

        for c in self.ctrls:
            minimum_config = to_buf(bytes(c._len))
            maximum_config = to_buf(bytes(c._len))
            current_config = to_buf(bytes(c._len))

            query_xu_control(self.fd, self.unit_id, c._selector, UVC_GET_MIN, minimum_config)
            query_xu_control(self.fd, self.unit_id, c._selector, UVC_GET_MAX, maximum_config)
            query_xu_control(self.fd, self.unit_id, c._selector, UVC_GET_CUR, current_config)

            c.min = minimum_config[c._offset][0]
            c.max = maximum_config[c._offset][0]
            c.value = current_config[c._offset][0]

            if c.type == 'menu':
                valmenu = find_by_value(c.menu, c.value)
                if valmenu:
                    c.value = valmenu.text_id


    def setup_ctrls(self, params):
        if not self.supported():
            return

        for k, v in params.items():
            ctrl = find_by_text_id(self.ctrls, k)
            if ctrl == None:
                continue
            if ctrl.type == 'menu':
                menu  = find_by_text_id(ctrl.menu, v)
                if menu == None:
                    logging.warning(f'LogitechBRIOCtrls: can\'t find {v} in {[c.text_id for c in ctrl.menu]}')
                    continue
                desired = menu.value
            elif ctrl.type == 'integer':
                desired = int(v)
            else:
                logging.warning(f'Can\'t set {k} to {v} (Unsupported control type {ctrl.type})')
                continue

            current_config = to_buf(bytes(ctrl._len))
            query_xu_control(self.fd, self.unit_id, ctrl._selector, UVC_GET_CUR, current_config)
            current_config[ctrl._offset] = desired
            query_xu_control(self.fd, self.unit_id, ctrl._selector, UVC_SET_CUR, current_config)
            query_xu_control(self.fd, self.unit_id, ctrl._selector, UVC_GET_CUR, current_config)
            current = current_config[ctrl._offset][0]

            if ctrl.type == 'menu':
                desmenu = find_by_value(ctrl.menu, desired)
                if desmenu:
                    desired = desmenu.text_id
                curmenu = find_by_value(ctrl.menu, current)
                if curmenu:
                    current = curmenu.text_id
            if current != desired:
                logging.warning(f'LogitechBRIOCtrls: failed to set {k} to {desired}, current value {current}\n')
                continue

            ctrl.value = desired

    def update_ctrls(self):
        return

    def get_ctrls(self):
        return self.ctrls

class V4L2Ctrl(BaseCtrl):
    def __init__(self, id, text_id, name, type, value, default = None, min = None, max = None, step = None, menu = None):
        super().__init__(text_id, name, type, value, default, min, max, step, menu)
        self._id = id

class V4L2Ctrls:
    to_type = {
        V4L2_CTRL_TYPE_INTEGER: 'integer',
        V4L2_CTRL_TYPE_BOOLEAN: 'boolean',
        V4L2_CTRL_TYPE_MENU: 'menu',
        V4L2_CTRL_TYPE_INTEGER_MENU: 'menu',
    }
    strtrans = bytes.maketrans(b' -', b'__')


    def __init__(self, device, fd):
        self.device = device
        self.fd = fd
        self.get_device_controls()


    def setup_ctrls(self, params):
        for k, v in params.items():
            ctrl = find_by_text_id(self.ctrls, k)
            if ctrl == None:
                continue
            intvalue = 0
            if ctrl.type == 'integer':
                intvalue = int(v)
            elif ctrl.type == 'boolean':
                intvalue = int(to_bool(v))
            elif ctrl.type == 'menu':
                menu = find_by_text_id(ctrl.menu, v)
                if menu == None:
                    logging.warning(f'V4L2Ctrls: Can\'t find {v} in {[c.text_id for c in ctrl.menu]}')
                    continue
                intvalue = menu.value
            else:
                logging.warning(f'V4L2Ctrls: Can\'t set {k} to {v} (Unsupported control type {ctrl.type})')
                continue
            try:
                new_ctrl = v4l2_control(ctrl._id, intvalue)
                ioctl(self.fd, VIDIOC_S_CTRL, new_ctrl)
                if new_ctrl.value != intvalue:
                    logging.warning(f'V4L2Ctrls: Can\'t set {k} to {v} using {new_ctrl.value} instead of {intvalue}')
                    continue
                
                if ctrl.type == 'menu':
                    ctrl.value = v
                else:
                    ctrl.value = intvalue
            except Exception as e:
                logging.warning(f'V4L2Ctrls: Can\'t set {k} to {v} ({e})')

    def get_device_controls(self):
        ctrls = []
        next_flag = V4L2_CTRL_FLAG_NEXT_CTRL | V4L2_CTRL_FLAG_NEXT_COMPOUND
        qctrl = v4l2_queryctrl(next_flag)
        while True:
            try:
                ioctl(self.fd, VIDIOC_QUERYCTRL, qctrl)
            except:
                break
            if qctrl.type in [V4L2_CTRL_TYPE_INTEGER, V4L2_CTRL_TYPE_BOOLEAN,
                V4L2_CTRL_TYPE_MENU, V4L2_CTRL_TYPE_INTEGER_MENU]:

                try:
                    ctrl = v4l2_control(qctrl.id)
                    ioctl(self.fd, VIDIOC_G_CTRL, ctrl)
                except:
                    logging.warning(f'V4L2Ctrls: Can\'t get ctrl {qctrl.name} value')

                text_id = self.to_text_id(qctrl.name)
                text = str(qctrl.name, 'utf-8')
                ctrl_type = V4L2Ctrls.to_type.get(qctrl.type)
                if ctrl_type == 'integer' and qctrl.minimum == 0 and qctrl.maximum == 1 and qctrl.step == 1:
                    ctrl_type = 'boolean'
                v4l2ctrl = V4L2Ctrl(qctrl.id, text_id, text, ctrl_type, int(ctrl.value),
                    qctrl.default, qctrl.minimum, qctrl.maximum, qctrl.step)

                # doesn't work, uvc driver bug?
                # v4l2ctrl.updater = bool(qctrl.flags & V4L2_CTRL_FLAG_UPDATE)
                v4l2ctrl.updater = qctrl.id in V4L2_CTRL_UPDATERS
                v4l2ctrl.inactive = bool(qctrl.flags & V4L2_CTRL_FLAG_INACTIVE)
                ctrl_info = V4L2_CTRL_INFO.get(qctrl.id)
                if ctrl_info != None:
                    v4l2ctrl.kernel_id = ctrl_info[0]
                    v4l2ctrl.tooltip = ctrl_info[1]

                if qctrl.type in [V4L2_CTRL_TYPE_MENU, V4L2_CTRL_TYPE_INTEGER_MENU]:
                    v4l2ctrl.menu = []
                    for i in range(qctrl.minimum, qctrl.maximum + 1):
                        try:
                            qmenu = v4l2_querymenu(qctrl.id, i)
                            ioctl(self.fd, VIDIOC_QUERYMENU, qmenu)
                        except:
                            continue
                        if qctrl.type == V4L2_CTRL_TYPE_MENU:
                            menu_text = str(qmenu.name, 'utf-8')
                            menu_text_id = self.to_text_id(qmenu.name)
                        else:
                            menu_text_id = str(qmenu.value)
                            menu_text = menu_text_id
                        v4l2menu = BaseCtrlMenu(menu_text_id, menu_text, int(qmenu.index))
                        v4l2ctrl.menu.append(v4l2menu)
                        if v4l2ctrl.value == qmenu.index:
                            v4l2ctrl.value = menu_text_id
                        if v4l2ctrl.default == qmenu.index:
                            v4l2ctrl.default = menu_text_id
                        
                ctrls.append(v4l2ctrl)
            qctrl = v4l2_queryctrl(qctrl.id | next_flag)



        # move the controls in the 'auto' control groups near each other
        for k, v in V4L2_CTRL_REORDERS.items():
            what = find_idx(ctrls, lambda c: c._id == k)
            where = find_idx(ctrls, lambda c: c._id == v)
            if what and where:
                ctrls.insert(where - 1 if what < where else where, ctrls.pop(what))

        self.ctrls = ctrls

    def update_ctrls(self):
        for c in self.ctrls:
            qctrl = v4l2_queryctrl(c._id)
            try:
                ioctl(self.fd, VIDIOC_QUERYCTRL, qctrl)
            except:
                logging.warning(f'V4L2Ctrls: Can\'t update ctrl {c.name} ')
                continue
            c.inactive = bool(qctrl.flags & V4L2_CTRL_FLAG_INACTIVE)

    def get_ctrls(self):
        return self.ctrls
    
    def to_text_id(self, text):
        return str(text.lower().translate(V4L2Ctrls.strtrans, delete = b',&(.)/').replace(b'__', b'_'), 'utf-8')

class V4L2FmtCtrls:
    def __init__(self, device, fd):
        self.device = device
        self.fd = fd
        self.ctrls = []
        self.get_format_ctrls()

    def get_ctrls(self):
        return self.ctrls
    
    def update_ctrls(self):
        return

    def setup_ctrls(self, params):
        for k, v in params.items():
            ctrl = find_by_text_id(self.ctrls, k)
            if ctrl == None:
                continue
            menu = find_by_text_id(ctrl.menu, v)
            if menu == None:
                logging.warning(f'V4L2FmtCtrls: Can\'t find {v} in {[c.text_id for c in ctrl.menu]}')
                continue
            if ctrl.text_id == 'pixelformat':
                self.set_pixelformat(ctrl, v)
            elif ctrl.text_id == 'resolution':
                self.set_resolution(ctrl, v)
            elif ctrl.text_id == 'fps':
                self.set_fps(ctrl, v)

    def get_format_ctrls(self):
        fmt = v4l2_format()
        fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE
        try:
            ioctl(self.fd, VIDIOC_G_FMT, fmt)
        except Exception as e:
            logging.warning(f'V4L2FmtCtrls: Can\'t get fmt {e}')
            return

        pixelformat = pxf2str(fmt.fmt.pix.pixelformat)
        resolution = wh2str(fmt.fmt.pix)

        fps = self.get_fps()

        fmts = self.get_fmts()
        resolutions = self.get_resolutions(fmt.fmt.pix.pixelformat)
        framerates = self.get_framerates(fmt.fmt.pix.pixelformat, fmt.fmt.pix.width, fmt.fmt.pix.height)

        self.ctrls = [
            # must reopen the fd, because changing these lock the device, and can't be open by another processes
            BaseCtrl('pixelformat', 'Pixel format', 'menu', pixelformat, reopener=True, tooltip='Output pixel format', menu=[
                BaseCtrlMenu(fmt, fmt, None) for fmt in fmts
            ]),
        ]
        if len(resolutions) > 0:
            self.ctrls.append(
                BaseCtrl('resolution', 'Resolution', 'menu', resolution, reopener=True, tooltip='Resolution in pixels', menu=[
                    BaseCtrlMenu(resolution, resolution, None) for resolution in resolutions
                ]),
            )
        if len(framerates) > 0:
            self.ctrls.append(
                BaseCtrl('fps', 'FPS', 'menu', fps, reopener=True, menu_dd=True,  tooltip='Frame per second', menu=[
                    BaseCtrlMenu(fps, fps, None) for fps in framerates
                ]), # fps menu should be dropdown
            )

    def set_pixelformat(self, ctrl, pixelformat):
        fmt = v4l2_format()
        fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE
        try:
            ioctl(self.fd, VIDIOC_G_FMT, fmt)
        except Exception as e:
            logging.warning(f'V4L2FmtCtrls: Can\'t get fmt {e}')
            return

        fmt.fmt.pix.pixelformat = str2pxf(pixelformat)

        try:
            ioctl(self.fd, VIDIOC_S_FMT, fmt)
        except Exception as e:
            logging.warning(f'V4L2FmtCtrls: Can\'t set fmt {e}')
            return

        if pxf2str(fmt.fmt.pix.pixelformat) != pixelformat:
            logging.warning(f'V4L2FmtCtrls: Can\'t set pixelformat to {pixelformat} using {pxf2str(fmt.fmt.pix.pixelformat)}')
            return
        
        ctrl.value = pixelformat

    def set_resolution(self, ctrl, resolution):
        fmt = v4l2_format()
        fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE
        try:
            ioctl(self.fd, VIDIOC_G_FMT, fmt)
        except Exception as e:
            logging.warning(f'V4L2FmtCtrls: Can\'t get fmt {e}')
            return

        str2wh(resolution, fmt.fmt.pix)

        try:
            ioctl(self.fd, VIDIOC_S_FMT, fmt)
        except Exception as e:
            logging.warning(f'V4L2FmtCtrls: Can\'t set fmt {e}')
            return

        if wh2str(fmt.fmt.pix) != resolution:
            logging.warning(f'V4L2FmtCtrls: Can\'t set resolution to {resolution} using {wh2str(fmt.fmt.pix)}')
            return

        ctrl.value = resolution

    def get_fps(self):
        parm = v4l2_streamparm()
        parm.type = V4L2_BUF_TYPE_VIDEO_CAPTURE
        try:
            ioctl(self.fd, VIDIOC_G_PARM, parm)
        except Exception as e:
            logging.warning(f'V4L2FmtCtrls: Can\'t get fps: {e}')
            return 0

        if parm.parm.capture.timeperframe.numerator == 0:
            return 0

        return dn2str(parm.parm.capture.timeperframe)

    def set_fps(self, ctrl, fps):
        parm = v4l2_streamparm()
        parm.type = V4L2_BUF_TYPE_VIDEO_CAPTURE
        parm.parm.capture.timeperframe.numerator = 1
        parm.parm.capture.timeperframe.denominator = int(fps)
        try:
            ioctl(self.fd, VIDIOC_S_PARM, parm)
        except Exception as e:
            logging.warning(f'V4L2FmtCtrls: Can\'t set fps: {e}')
            return
        
        tf = parm.parm.capture.timeperframe
        if tf.denominator == 0 or tf.numerator == 0:
            logging.warning(f'V4L2FmtCtrls: VIDIOC_S_PARM: Invalid frame rate {fps}')
            return
        if int(fps) != (tf.denominator / tf.numerator):
            logging.warning(f'V4L2FmtCtrls: Can\'t set fps to {fps} using {tf.denominator / tf.numerator}')
            return
        
        ctrl.value = fps

    def get_fmts(self):
        fmts = []
        fmt = v4l2_fmtdesc()
        fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE
        while True:
            try:
                ioctl(self.fd, VIDIOC_ENUM_FMT, fmt)
            except:
                break
            fmts.append(pxf2str(fmt.pixelformat))
            fmt.index += 1
        return fmts

    def get_resolutions(self, pixelformat):
        resolutions = []
        frm = v4l2_frmsizeenum()
        frm.pixel_format = pixelformat
        while True:
            try:
                ioctl(self.fd, VIDIOC_ENUM_FRAMESIZES, frm)
            except:
                break
            if frm.type != V4L2_FRMSIZE_TYPE_DISCRETE:
                break
            resolutions.append(wh2str(frm.discrete))
            frm.index += 1
        return resolutions

    def get_framerates(self, pixelformat, width, height):
        framerates = []
        frmi = v4l2_frmivalenum()
        frmi.pixel_format = pixelformat
        frmi.width = width
        frmi.height = height
        while True:
            try:
                ioctl(self.fd, VIDIOC_ENUM_FRAMEINTERVALS, frmi)
            except:
                break
            if frmi.type != V4L2_FRMIVAL_TYPE_DISCRETE:
                break
            framerates.append(dn2str(frmi.discrete))
            frmi.index += 1
        return framerates

def str2pxf(str):
    return ord(str[0]) | (ord(str[1]) << 8) | (ord(str[2]) << 16) | (ord(str[3]) << 24)

def pxf2str(pxf):
    return chr(pxf & 0xff) + chr(pxf >> 8 & 0xff) + chr(pxf >> 16 & 0xff) + chr(pxf >> 24 & 0xff)

def wh2str(wh):
    return f'{wh.width}x{wh.height}'

def str2wh(str, wh):
    split = str.split('x')
    wh.width = int(split[0])
    wh.height = int(split[1])

def dn2str(dn):
    return f'{dn.denominator//dn.numerator}'



class SystemdSaver:
    def __init__(self, cam_ctrls):
        self.cam_ctrls = cam_ctrls
        self.ctrls = [] if not self.systemd_available() else [
            BaseCtrl('systemd_save', 'Save settings to Systemd', 'button',
                menu = [ BaseCtrlMenu('save', 'Save', 'save') ], tooltip = 'Save settings into a systemd path triggered user service',
            )
        ]
    
    def systemd_available(self):
        return os.path.exists('/bin/systemctl')

    def get_ctrls(self):
        return self.ctrls
    
    def update_ctrls(self):
        return
    
    def setup_ctrls(self, params):
        for k, v in params.items():
            ctrl = find_by_text_id(self.ctrls, k)
            if ctrl == None:
                continue
            menu = find_by_text_id(ctrl.menu, v)
            if menu == None:
                logging.warning(f'SystemdSaver: Can\'t find {v} in {[c.text_id for c in ctrl.menu]}')
                continue
            if menu.text_id == 'save':
                self.create_systemd_service_and_path()

    def create_systemd_service_and_path(self):
        device = self.cam_ctrls.device
        dev_id = os.path.basename(device)
        controls = self.get_claimed_controls()
        
        service_file_str = self.get_service_file(sys.path[0], device, dev_id, controls)
        path_file_str = self.get_path_file(device)

        systemd_user_dir = os.path.expanduser('~/.config/systemd/user')
        prefix = 'cameractrls'

        service_file = f'{prefix}-{dev_id}.service'
        path_file = f'{prefix}-{dev_id}.path'

        os.makedirs(systemd_user_dir, exist_ok=True)

        with open(f'{systemd_user_dir}/{service_file}', 'w', encoding="utf-8") as f:
            f.write(service_file_str)

        with open(f'{systemd_user_dir}/{path_file}', 'w', encoding="utf-8") as f:
            f.write(path_file_str)
        
        subprocess.run(["systemctl", "--user", "enable", "--now", service_file])
        subprocess.run(["systemctl", "--user", "enable", "--now", path_file])

    def get_claimed_controls(self):
        ctrls = [
            f'{c.text_id}={c.value}'
            for c in self.cam_ctrls.get_ctrls()
            if not c.inactive and c.value != None and c.value != c.default
        ]
        return ','.join(ctrls)

    def get_service_file(self, script_path, device, dev_id, controls):
        return f"""[Unit]
Description=Restore {dev_id} controls

[Service]
Type=oneshot
ExecStart={script_path}/cameractrls.py -d {device} -c {controls}

[Install]
WantedBy=graphical-session.target
"""

    def get_path_file(self, device):
        return f"""[Unit]
Description=Watch {device} and restore controls

[Path]
PathExists={device}

[Install]
WantedBy=paths.target
"""

class CtrlPage:
    def __init__(self, title, categories, target='main'):
        self.title = title
        self.categories = categories
        self.target = target

class CtrlCategory:
    def __init__(self, title, ctrls):
        self.title = title
        self.ctrls = ctrls

class CameraCtrls:
    def __init__(self, device, fd):
        self.device = device
        self.fd = fd
        self.ctrls = [
            V4L2Ctrls(device, fd),
            V4L2FmtCtrls(device, fd),
            KiyoProCtrls(device, fd),
            LogitechCtrls(device, fd),
            LogitechBRIOCtrls(device, fd),
            SystemdSaver(self),
        ]
    
    def print_ctrls(self):
        for page in self.get_ctrl_pages():
            for cat in page.categories:
                print(f'{page.title} / {cat.title}')
                for c in cat.ctrls:
                    print(f' {c.text_id}', end = '')
                    if c.type == 'menu':
                        print(f' = {c.value}\t( ', end = '')
                        if c.default:
                            print(f'default: {c.default} ', end = '')
                        print('values:', end = ' ')
                        print(', '.join([m.text_id for m in c.menu]), end = ' )')
                    elif c.type == 'button':
                        print('\t\t( buttons: ', end = '')
                        print(', '.join([m.text_id for m in c.menu]), end = ' )')
                    elif c.type in ['integer', 'boolean']:
                        print(f' = {c.value}\t( default: {c.default} min: {c.min} max: {c.max}', end = '')
                        if c.step != 1:
                            print(f' step: {c.step}', end = '')
                        print(' )', end = '')
                    if c.updater:
                        print(' | updater', end = '')
                    if c.inactive:
                        print(' | inactive', end = '')
                    print()
    
    def setup_ctrls(self, params):
        for c in self.ctrls:
            c.setup_ctrls(params)
        unknown_ctrls = list(set(params.keys()) - set([c.text_id for c in self.get_ctrls()]))
        if len(unknown_ctrls) > 0:
            logging.warning(f'CameraCtrls: can\'t find {unknown_ctrls} controls')

    def update_ctrls(self):
        for c in self.ctrls:
            c.update_ctrls()

    def get_ctrls(self):
        ctrls = []
        for c in self.ctrls:
            ctrls += c.get_ctrls()
        return ctrls

    def get_ctrl_pages(self):
        ctrls = self.get_ctrls()
        pages = [
            CtrlPage('Crop', [
                CtrlCategory('Crop', pop_list_by_text_ids(ctrls, ['kiyo_pro_fov', 'logitech_brio_fov', 'zoom_absolute', 'pan_absolute', 'tilt_absolute'])),
            ]),
            CtrlPage('Color', [
                CtrlCategory('Color', pop_list_by_text_ids(ctrls, ['white_balance', 'brightness', 'contrast', 'saturation', 'sharpness', 'hue', 'gamma'])),
            ]),
            CtrlPage('Exposure', [
                CtrlCategory('Exposure', pop_list_by_text_ids(ctrls,
                    ['exposure', 'auto_exposure', 'backlight_compensation', 'gain'])),
                CtrlCategory('HDR', pop_list_by_text_ids(ctrls, ['kiyo_pro_hdr'])),
            ]),
            CtrlPage('Advanced', [
                CtrlCategory('Focus', pop_list_by_text_ids(ctrls, ['focus', 'kiyo_pro_af_mode'])),
                CtrlCategory('Power Line', pop_list_by_text_ids(ctrls, ['power_line_frequency'])),
                CtrlCategory('ISO', pop_list_by_text_ids(ctrls, ['iso'])),
                CtrlCategory('Color Effects', pop_list_by_text_ids(ctrls, ['color_effects'])),
                CtrlCategory('Rotate/Flip', pop_list_by_text_ids(ctrls, ['rotate', 'horizontal_flip', 'vertical_flip'])),
            ]),
            CtrlPage('Compression', [
                CtrlCategory('H264', pop_list_by_text_ids(ctrls, ['h264_', 'video_bitrate', 'repeat_sequence_header'])),
                CtrlCategory('JPEG', pop_list_by_text_ids(ctrls, ['compression_quality'])),
            ]),
            CtrlPage('Capture', [
                CtrlCategory('Capture', pop_list_by_text_ids(ctrls, ['pixelformat', 'resolution', 'fps'])),
            ]),
            CtrlPage('Settings', [
                CtrlCategory('Save', pop_list_by_text_ids(ctrls, ['systemd_save', 'kiyo_pro_save'])),
            ], target='footer')
        ]
        pages[3].categories += CtrlCategory('Other', ctrls), #the rest
        
        # filter out the empty categories and pages
        for page in pages:
            page.categories = [cat for cat in page.categories if len(cat.ctrls)]
        pages = [page for page in pages if len(page.categories)]

        return pages


def usage():
    print(f'usage: {sys.argv[0]} [--help] [-d DEVICE] [--list] [-c CONTROLS]\n')
    print(f'optional arguments:')
    print(f'  -h, --help         show this help message and exit')
    print(f'  -d DEVICE          use DEVICE, default /dev/video0')
    print(f'  -l, --list         list the controls and values')
    print(f'  -L, --list-devices list capture devices')
    print(f'  -c CONTROLS        set CONTROLS (eg.: hdr=on,fov=wide)')
    print()
    print(f'example:')
    print(f'  {sys.argv[0]} -c brightness=128,kiyo_pro_hdr=on,kiyo_pro_fov=wide')

def main():
    try:
        arguments, values = getopt.getopt(sys.argv[1:], 'hd:lLc:', ['help', 'list', 'list-devices'])
    except getopt.error as err:
        print(err)
        usage()
        sys.exit(2)

    if len(arguments) == 0:
        usage()
        sys.exit(0)

    list_controls = False
    list_devices = False
    device = '/dev/video0'
    controls = ''

    for current_argument, current_value in arguments:
        if current_argument in ('-h', '--help'):
            usage()
            sys.exit(0)
        elif current_argument in ('-d', '--device'):
            device = current_value
        elif current_argument in ('-l', '--list'):
            list_controls = True
        elif current_argument in ('-L', '--list-devices'):
            list_devices = True
        elif current_argument in ('-c'):
            controls = current_value

    if list_devices:
        for d in get_devices(v4ldirs):
            print(d)
        sys.exit(0)

    try:
        fd = os.open(device, os.O_RDWR, 0)
    except Exception as e:
        logging.error(f'os.open({device}, os.O_RDWR, 0) failed: {e}')
        sys.exit(2)

    camera_ctrls = CameraCtrls(device, fd)

    if list_controls:
        camera_ctrls.print_ctrls()

    if controls != '':
        ctrlsmap = {}
        for control in controls.split(','):
            kv = control.split('=', maxsplit=1)
            if len(kv) != 2:
                logging.warning(f'invalid value: {control}')
                continue
            ctrlsmap[kv[0]]=kv[1]

        camera_ctrls.setup_ctrls(ctrlsmap)

if __name__ == '__main__':
    main()
