#!/usr/bin/env python3

import sys, os, ctypes, ctypes.util, logging, getopt, time
from collections import namedtuple
from struct import unpack_from, calcsize
from cameractrls import CameraCtrls, find_symlink_in, get_configfilename

clib = ctypes.util.find_library('c')
if clib is None:
    logging.error('libc not found, please install the libc package!')
    sys.exit(2)
c = ctypes.CDLL(clib)

logging.getLogger().setLevel(logging.INFO)

inotify_init1 = c.inotify_init1
inotify_init1.restype = ctypes.c_int
inotify_init1.argtypes = [ctypes.c_int]
# int inotify_init1(int flags);

inotify_add_watch = c.inotify_add_watch
inotify_add_watch.restype = ctypes.c_int
inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
# int inotify_add_watch(int fd, const char *pathname, uint32_t mask);

inotify_rm_watch = c.inotify_rm_watch
inotify_rm_watch.restypes = ctypes.c_int
inotify_rm_watch.argtypes = [ctypes.c_int, ctypes.c_int]
# int inotify_rm_watch(int fd, int wd);

IN_CLOEXEC = os.O_CLOEXEC
IN_NONBLOCK = os.O_NONBLOCK

IN_ACCESS =	0x00000001 # File was accessed
IN_MODIFY =	0x00000002 # File was modified
IN_ATTRIB =	0x00000004 # Metadata changed
IN_CLOSE_WRITE = 0x00000008 # Writable file was closed
IN_CLOSE_NOWRITE = 0x00000010 # Unwritable file closed
IN_OPEN	= 0x00000020 # File was opened
IN_MOVED_FROM = 0x00000040 # File was moved from X
IN_MOVED_TO = 0x00000080 # File was moved to Y
IN_CREATE = 0x00000100 # Subfile was created
IN_DELETE = 0x00000200 # Subfile was deleted
IN_DELETE_SELF = 0x00000400 # Self was deleted
IN_MOVE_SELF = 0x00000800 # Self was moved

IN_ALL_EVENTS = ( \
    IN_ACCESS | IN_MODIFY | IN_ATTRIB | IN_CLOSE_WRITE | \
    IN_CLOSE_NOWRITE | IN_OPEN | IN_MOVED_FROM | \
    IN_MOVED_TO | IN_DELETE | IN_CREATE | IN_DELETE_SELF | \
    IN_MOVE_SELF \
)

IN_UNMOUNT = 0x00002000 # Backing fs was unmounted
IN_Q_OVERFLOW = 0x00004000 # Event queued overflowed
IN_IGNORED = 0x00008000 # File was ignored

IN_CLOSE = (IN_CLOSE_WRITE | IN_CLOSE_NOWRITE)
IN_MOVE	= (IN_MOVED_FROM | IN_MOVED_TO)

IN_ONLYDIR = 0x01000000 # only watch the path if it is a directory
IN_DONT_FOLLOW = 0x02000000 # don't follow a sym link
IN_EXCL_UNLINK = 0x04000000 # exclude events on unlinked objects
IN_MASK_CREATE = 0x10000000 # only create watches
IN_MASK_ADD = 0x20000000 # add to the mask of an already existing watch
IN_ISDIR = 0x40000000 # event occurred against dir
IN_ONESHOT = 0x80000000 # only send event once

NAME_MAX = 255

def usage():
    print(f'usage: {sys.argv[0]} [--help]\n')
    print(f'optional arguments:')
    print(f'  -h, --help         show this help message and exit')

def preset_device(device):
    logging.debug(f'trying to preset_device: {device}')

    configfile = get_configfilename(device)

    # if config file does not exists, we should not open the device
    if not os.path.exists(configfile):
        logging.debug(f'preset_device: {configfile} does not exists')
        return

    logging.info(f'preset_device: {device}')

    try:
        fd = os.open(device, os.O_RDWR, 0)
    except Exception as e:
        logging.warning(f'os.open({device}, os.O_RDWR, 0) failed: {e}')
        return

    errs = []

    camera_ctrls = CameraCtrls(device, fd)
    camera_ctrls.setup_ctrls({'preset': 'load_1'}, errs)
    if errs:
        logging.warning(f'preset_device: failed to load_1: {errs}')

    os.close(fd)

Event = namedtuple('Event', ['wd', 'mask', 'cookie', 'namesize', 'name'])
EVENT_FMT = 'iIII'
EVENT_SIZE = calcsize(EVENT_FMT)

def parse_events(data):
    pos = 0
    events = []
    while pos < len(data):
        wd, mask, cookie, namesize = unpack_from(EVENT_FMT, data, pos)
        pos += EVENT_SIZE + namesize
        name = data[pos - namesize : pos].split(b'\x00', 1)[0]
        events.append(Event(wd, mask, cookie, namesize, name.decode()))
    return events

def main():
    try:
        arguments, values = getopt.getopt(sys.argv[1:], 'h', ['help'])
    except getopt.error as err:
        print(err)
        usage()
        return 2

    for current_argument, current_value in arguments:
        if current_argument in ('-h', '--help'):
            usage()
            return 0

    dev_path = '/dev'
    v4l_paths = ['/dev/v4l/by-id/', '/dev/v4l/by-path/']

    for v4l_path in v4l_paths:
        for dirpath, dirs, files in os.walk(v4l_path):
            for device in files:
                preset_device(os.path.join(v4l_path, device))

    fd = inotify_init1(0)
    if fd == -1:
        logging.error(f'inotify_init1 failed')
        return 1

    wd = inotify_add_watch(fd, dev_path.encode(), IN_CREATE)
    if wd == -1:
        logging.error(f'inotify_add_watch failed {dev_path}')
        return 1

    while True:
        data = os.read(fd, EVENT_SIZE + NAME_MAX + 1)
        for e in parse_events(data):
            logging.debug(f'event: {e}')
            if e.name.startswith('video'):
                time.sleep(2) # waiting for udev to create dirs
                path = find_symlink_in(os.path.join(dev_path, e.name), v4l_paths)
                if path is None:
                    logging.warning(f'can\'t find {e.name} in {v4l_paths}')
                    continue
                preset_device(path.path)

if __name__ == '__main__':
    sys.exit(main())
