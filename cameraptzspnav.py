#!/usr/bin/env python3

import sys, os, ctypes, ctypes.util, logging, getopt, select, signal
from cameractrls import CameraCtrls, PTZController

spnavlib = ctypes.util.find_library('spnav')
if spnavlib is None:
    logging.error('spnav not found, please install the libspnav package!')
    sys.exit(2)
spnav = ctypes.CDLL(spnavlib)

#logging.getLogger().setLevel(logging.INFO)

enum = ctypes.c_uint

spnav_event_type = enum
(
    SPNAV_EVENT_ANY,	# used by spnav_remove_events()
    SPNAV_EVENT_MOTION,
    SPNAV_EVENT_BUTTON,	# includes both press and release
) = range(3)

class spnav_event_motion(ctypes.Structure):
    _fields_ = [
        ('type', ctypes.c_int),
        ('x', ctypes.c_int),
        ('y', ctypes.c_int),
        ('z', ctypes.c_int),
        ('rx', ctypes.c_int),
        ('ry', ctypes.c_int),
        ('rz', ctypes.c_int),
        ('period', ctypes.c_uint),
        ('data', ctypes.POINTER(ctypes.c_int)),
    ]

class spnav_event_button(ctypes.Structure):
    _fields_ = [
        ('type', ctypes.c_int),
        ('press', ctypes.c_int),
        ('bnum', ctypes.c_int),
    ]

class spnav_event(ctypes.Union):
    _fields_ = [
        ('type', ctypes.c_int),
        ('motion', spnav_event_motion),
        ('button', spnav_event_button),
    ]

spnav_open = spnav.spnav_open
spnav_open.restype = ctypes.c_int
spnav_open.argtypes = []
# int spnav_open(void);

spnav_dev_name = spnav.spnav_dev_name
spnav_dev_name.restype = ctypes.c_int
spnav_dev_name.argtypes = [ctypes.c_char_p, ctypes.c_int]
# int spnav_dev_name(char *buf, int bufsz);

spnav_fd = spnav.spnav_fd
spnav_fd.restype = ctypes.c_int
spnav_fd.argtypes = []
# int spnav_fd(void);

spnav_poll_event = spnav.spnav_poll_event
spnav_poll_event.restype = ctypes.c_int
spnav_poll_event.argtypes = [ctypes.POINTER(spnav_event)]
# int spnav_poll_event(spnav_event *event);

spnav_close = spnav.spnav_close
spnav_close.restype = ctypes.c_int
spnav_close.argtypes = []
# int spnav_close(void);

th = 133

def check_step(cb, value):
    if -th < value < th:
        return 0
    value = round(value/128)
    return cb(value, [])

def check_speed(cb, value):
    if -th < value < th:
        value = 0
    value = round(value/128)
    return cb(value, [])

def usage():
    print(f'usage: {sys.argv[0]} [-h] [-l] [-c] [-d DEVICE]\n')
    print(f'optional arguments:')
    print(f'  -h, --help        show this help message and exit')
    print(f'  -l, --list        list space navigators')
    print(f'  -c, --controller  use space navigator (0..n), default first')
    print(f'  -d DEVICE         use DEVICE, default /dev/video0')
    print()
    print(f'example:')
    print(f'  {sys.argv[0]} -d /dev/video4')

def main():
    try:
        arguments, values = getopt.getopt(sys.argv[1:], 'hlc:d:', ['help', 'list', 'controller', 'device'])
    except getopt.error as err:
        print(err)
        usage()
        sys.exit(2)

    list_ctrls = False
    device = '/dev/video0'

    for current_argument, current_value in arguments:
        if current_argument in ('-h', '--help'):
            usage()
            sys.exit(0)
        elif current_argument in ('-l', '--list'):
            list_ctrls = True
        elif current_argument in ('-d', '--device'):
            device = current_value

    if spnav_open() == -1:
        logging.error(f'spnav_open failed')
        sys.exit(1)
    
    if list_ctrls:
        # only one device is supported by the libspnav
        name = ctypes.create_string_buffer(64)
        if spnav_dev_name(name, 64) < 0:
            logging.warning(f'spnav_dev_name failed')
        else:
            n = name.raw.decode().strip('\0')
            print(f'{n}:0')
        sys.exit(0)

    try:
        fd = os.open(device, os.O_RDWR, 0)
    except Exception as e:
        logging.error(f'os.open({device}, os.O_RDWR, 0) failed: {e}')
        sys.exit(2)

    camera_ctrls = CameraCtrls(device, fd)
    if not camera_ctrls.has_ptz():
        logging.error(f'camera {device} cannot do PTZ')
        sys.exit(1)

    ptz = PTZController(camera_ctrls)

    epoll = select.epoll()
    epoll.register(spnav_fd(), select.POLLIN | select.POLLERR | select.POLLNVAL)

    signal.signal(signal.SIGINT, lambda signum, frame: epoll.close())
    event = spnav_event()
    while not epoll.closed:
        try:
            p = epoll.poll()
        except OSError:
            break

        if len(p) == 0:
            continue
        (fd , v) = p[0]
        if v == select.POLLERR:
            logging.warning(f'POLLERR')
            break

        if v == select.POLLNVAL:
            logging.warning(f'POLLNVAL')
            break

        if spnav_poll_event(event) == 0:
            logging.warning(f'spnav_poll_event failed')
            continue

        if event.type == SPNAV_EVENT_MOTION:            
            check_step(ptz.do_zoom_step, event.motion.z)
            check_step(ptz.do_pan_step, event.motion.x)
            check_step(ptz.do_tilt_step, event.motion.y)
            check_speed(ptz.do_pan_speed, -event.motion.ry)
            check_speed(ptz.do_tilt_speed, event.motion.rx)
        elif event.type == SPNAV_EVENT_BUTTON:
            if event.button.bnum == 1 and event.button.press == 0:
                ptz.do_reset([])

    spnav_close()

if __name__ == '__main__':
    sys.exit(main())
