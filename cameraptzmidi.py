#!/usr/bin/env python3

import sys, os, ctypes, ctypes.util, logging, getopt, select, asyncio, signal
from cameractrls import CameraCtrls, PTZController

asoundlib = ctypes.util.find_library('asound')
if asoundlib is None:
    logging.error('libasound not found, please install the alsa-lib package!')
    sys.exit(2)
asound = ctypes.CDLL(asoundlib)

#logging.getLogger().setLevel(logging.INFO)

SND_SEQ_OPEN_INPUT = 2

SND_SEQ_PORT_CAP_READ = (1<<0)
SND_SEQ_PORT_CAP_WRITE	= (1<<1)
SND_SEQ_PORT_CAP_SUBS_READ = (1<<5)
SND_SEQ_PORT_CAP_SUBS_WRITE = (1<<6)

SND_SEQ_PORT_TYPE_HARDWARE = (1<<16)
SND_SEQ_PORT_TYPE_APPLICATION = (1<<20)

SND_SEQ_EVENT_CONTROLLER = 10
SND_SEQ_EVENT_PGMCHANGE = 11
SND_SEQ_EVENT_PORT_UNSUBSCRIBED = 67

snd_seq_p = ctypes.c_void_p

snd_seq_client_type_t = ctypes.c_uint
snd_seq_event_type_t = ctypes.c_ubyte
snd_seq_tick_time_t = ctypes.c_uint

class snd_seq_client_info(ctypes.Structure):
    _fields_ = [
        ('client', ctypes.c_int),
        ('type', snd_seq_client_type_t),
        ('name', ctypes.c_char * 64),
        ('filter', ctypes.c_uint),
        ('multicast_filter', ctypes.c_ubyte * 8),
        ('num_ports', ctypes.c_int),
        ('event_lost', ctypes.c_int),
        ('card', ctypes.c_int),
        ('pid', ctypes.c_int),
        ('midi_version', ctypes.c_uint),
        ('group_filter', ctypes.c_uint),
        ('reserved', ctypes.c_char * 48),
    ]

class snd_seq_addr(ctypes.Structure):
    _fields_ = [
        ('client', ctypes.c_ubyte),
        ('port', ctypes.c_ubyte),
    ]

class snd_seq_port_info(ctypes.Structure):
    _fields_ = [
        ('addr', snd_seq_addr),
        ('name', ctypes.c_char * 64),
        ('capability', ctypes.c_uint),
        ('type', ctypes.c_uint),
        ('midi_channels', ctypes.c_int),
        ('midi_voices', ctypes.c_int),
        ('synth_voices', ctypes.c_int),
        ('read_use', ctypes.c_int),
        ('write_use', ctypes.c_int),
        ('kernel', ctypes.c_void_p),
        ('flags', ctypes.c_uint),
        ('time_queue', ctypes.c_ubyte),
        ('direction', ctypes.c_ubyte),
        ('ump_group', ctypes.c_ubyte),
        ('reserved', ctypes.c_char * 57),
    ]

class snd_seq_real_time(ctypes.Structure):
    _fields_ = [
        ('tv_sec', ctypes.c_uint),
        ('tv_nsec', ctypes.c_uint),
    ]

class snd_seq_timestamp(ctypes.Union):
    _fields_ = [
        ('tick', snd_seq_tick_time_t),
        ('time', snd_seq_real_time),
    ]

class snd_seq_ev_ctrl(ctypes.Structure):
    _fields_ = [
        ('channel', ctypes.c_ubyte),
        ('unused1', ctypes.c_ubyte),
        ('unused2', ctypes.c_ubyte),
        ('unused3', ctypes.c_ubyte),
        ('param', ctypes.c_uint),
        ('value', ctypes.c_int),
    ]

class snd_seq_event_data(ctypes.Union):
    _fields_ = [
        ('control', snd_seq_ev_ctrl),
    ]

class snd_seq_event(ctypes.Structure):
    _fields_ = [
        ('type', snd_seq_event_type_t),
        ('flags', ctypes.c_ubyte),
        ('tag', ctypes.c_char),
        ('queue', ctypes.c_ubyte),
        ('time', snd_seq_timestamp),
        ('source', snd_seq_addr),
        ('dest', snd_seq_addr),
        ('data', snd_seq_event_data),
    ]

class pollfd(ctypes.Structure):
    _fields_ =  [
        ('fd', ctypes.c_int),
        ('events', ctypes.c_short),
        ('revents', ctypes.c_short),
    ]

snd_seq_client_info_p = ctypes.POINTER(snd_seq_client_info)
snd_seq_port_info_p = ctypes.POINTER(snd_seq_port_info)
snd_seq_event_p = ctypes.POINTER(snd_seq_event)

snd_seq_open = asound.snd_seq_open
snd_seq_open.restype = ctypes.c_int
snd_seq_open.argtypes = [ctypes.POINTER(snd_seq_p), ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
# int snd_seq_open(snd_seq_t **seq, const char *name, int streams, int mode);

snd_seq_set_client_name = asound.snd_seq_set_client_name
snd_seq_set_client_name.restype = ctypes.c_int
snd_seq_set_client_name.argtypes = [snd_seq_p, ctypes.c_char_p]
# int snd_seq_set_client_name(snd_seq_t *seq, const char *name);

snd_seq_create_simple_port = asound.snd_seq_create_simple_port
snd_seq_create_simple_port.restype = ctypes.c_int
snd_seq_create_simple_port.argtypes = [snd_seq_p, ctypes.c_char_p, ctypes.c_uint, ctypes.c_uint]
# int snd_seq_create_simple_port(snd_seq_t *seq, const char *name, unsigned int caps, unsigned int type);

snd_seq_client_info_set_client = asound.snd_seq_client_info_set_client
snd_seq_client_info_set_client.restype = None
snd_seq_client_info_set_client.argtypes = [snd_seq_client_info_p, ctypes.c_int]
# void snd_seq_client_info_set_client(snd_seq_client_info_t *info, int client);

snd_seq_query_next_client = asound.snd_seq_query_next_client
snd_seq_query_next_client.restype = ctypes.c_int
snd_seq_query_next_client.argtypes = [snd_seq_p, snd_seq_client_info_p]
# int snd_seq_query_next_client(snd_seq_t *handle, snd_seq_client_info_t *info);

snd_seq_client_info_get_client = asound.snd_seq_client_info_get_client
snd_seq_client_info_get_client.restype = ctypes.c_int
snd_seq_client_info_get_client.argtypes = [snd_seq_client_info_p]
# int snd_seq_client_info_get_client(const snd_seq_client_info_t *info);

snd_seq_port_info_set_client = asound.snd_seq_port_info_set_client
snd_seq_port_info_set_client.restype = None
snd_seq_port_info_set_client.argtypes = [snd_seq_port_info_p, ctypes.c_int]
# void snd_seq_port_info_set_client(snd_seq_port_info_t *info, int client);

snd_seq_port_info_set_port = asound.snd_seq_port_info_set_port
snd_seq_port_info_set_port.restype = None
snd_seq_port_info_set_port.argtypes = [snd_seq_port_info_p, ctypes.c_int]
# void snd_seq_port_info_set_port(snd_seq_port_info_t *info, int port);

snd_seq_query_next_port = asound.snd_seq_query_next_port
snd_seq_query_next_port.restype = ctypes.c_int
snd_seq_query_next_port.argtypes = [snd_seq_p, snd_seq_port_info_p]
# int snd_seq_query_next_port(snd_seq_t *handle, snd_seq_port_info_t *info);

snd_seq_port_info_get_capability = asound.snd_seq_port_info_get_capability
snd_seq_port_info_get_capability.restype = ctypes.c_uint
snd_seq_port_info_get_capability.argtypes = [snd_seq_port_info_p]
# unsigned int snd_seq_port_info_get_capability(const snd_seq_port_info_t *info);

snd_seq_port_info_get_type = asound.snd_seq_port_info_get_type
snd_seq_port_info_get_type.restype = ctypes.c_uint
snd_seq_port_info_get_type.argtypes = [snd_seq_port_info_p]
# unsigned int snd_seq_port_info_get_type(const snd_seq_port_info_t *info);

snd_seq_port_info_get_port = asound.snd_seq_port_info_get_port
snd_seq_port_info_get_port.restype = ctypes.c_int
snd_seq_port_info_get_port.argtypes = [snd_seq_port_info_p]
# int snd_seq_port_info_get_port(const snd_seq_port_info_t *info);

snd_seq_port_info_get_name = asound.snd_seq_port_info_get_name
snd_seq_port_info_get_name.restype = ctypes.c_char_p
snd_seq_port_info_get_name.argtypes = [snd_seq_port_info_p]
# const char *snd_seq_port_info_get_name(const snd_seq_port_info_t *info)

snd_seq_set_client_event_filter = asound.snd_seq_set_client_event_filter
snd_seq_set_client_event_filter.restype = ctypes.c_int
snd_seq_set_client_event_filter.argtypes = [snd_seq_p, ctypes.c_int]
# void snd_seq_set_client_event_filter(snd_seq_t *seq, int event_type);

snd_seq_connect_from = asound.snd_seq_connect_from
snd_seq_connect_from.restype = ctypes.c_int
snd_seq_connect_from.argtypes = [snd_seq_p, ctypes.c_int, ctypes.c_int, ctypes.c_int]
# int snd_seq_connect_from(snd_seq_t *seq, int my_port, int src_client, int src_port);

snd_seq_poll_descriptors_count = asound.snd_seq_poll_descriptors_count
snd_seq_poll_descriptors_count.restype = ctypes.c_int
snd_seq_poll_descriptors_count.argtypes = [snd_seq_p, ctypes.c_short]
# int snd_seq_poll_descriptors_count(snd_seq_t *handle, short events);

snd_seq_poll_descriptors = asound.snd_seq_poll_descriptors
snd_seq_poll_descriptors.restype = ctypes.c_int
snd_seq_poll_descriptors.argtypes = [snd_seq_p, ctypes.POINTER(pollfd), ctypes.c_uint, ctypes.c_short]
# int snd_seq_poll_descriptors(snd_seq_t *handle, struct pollfd *pfds, unsigned int space, short events);

snd_seq_event_input_pending = asound.snd_seq_event_input_pending
snd_seq_event_input_pending.restype = ctypes.c_int
snd_seq_event_input_pending.argtypes = [snd_seq_p, ctypes.c_int]
# int snd_seq_event_input_pending(snd_seq_t *seq, int fetch_sequencer);

snd_seq_event_input = asound.snd_seq_event_input
snd_seq_event_input.restype = ctypes.c_int
snd_seq_event_input.argtypes = [snd_seq_p, ctypes.POINTER(snd_seq_event_p)]
# int snd_seq_event_input(snd_seq_t *handle, snd_seq_event_t **ev);

def get_hw_client_ports(seq):
    cinfo = snd_seq_client_info()
    pinfo = snd_seq_port_info()
    ret = []

    snd_seq_client_info_set_client(cinfo, -1)
    while snd_seq_query_next_client(seq, cinfo) >= 0:
        client = snd_seq_client_info_get_client(cinfo)

        snd_seq_port_info_set_client(pinfo, client)
        snd_seq_port_info_set_port(pinfo, -1)
        while snd_seq_query_next_port(seq, pinfo) >= 0:
            if (snd_seq_port_info_get_capability(pinfo)
                & (SND_SEQ_PORT_CAP_READ | SND_SEQ_PORT_CAP_SUBS_READ)) \
                != (SND_SEQ_PORT_CAP_READ | SND_SEQ_PORT_CAP_SUBS_READ):
                continue

            if not(snd_seq_port_info_get_type(pinfo) & SND_SEQ_PORT_TYPE_HARDWARE):
                continue

            port = snd_seq_port_info_get_port(pinfo)
            name = snd_seq_port_info_get_name(pinfo)
            ret.append((name.decode(), client, port))
    return ret

def check_cc(ev, cc, cb):
    if ev.data.control.param != cc or ev.data.control.value != 0:
        return

    cb([])

def check_abs_knob(ev, cc, cb):
    if ev.data.control.param != cc:
        return

    cb(ev.data.control.value / 127, [])

def check_rel_knob(ev, cc, cb, loop=None):
    if ev.data.control.param != cc:
        return

    if ev.data.control.value in [127, 126, 125]:
        step = ev.data.control.value - 128 #-1, -2, -3
    elif ev.data.control.value in [1, 2, 3]:
        step = ev.data.control.value
    else:
        return

    cb(step, [])

    if loop is None:
        return

    # rel knobs emit 1, 2, 3 or 127, 126, 125 only, set to 0 after a while
    if cc in loop.ctx:
        loop.ctx[cc].cancel()
    loop.ctx[cc] = loop.call_later(0.1, cb, 0, [])

def check_joy(ev, cc, cb, loop=None):
    if ev.data.control.param != cc:
        return

    value = round((ev.data.control.value - 64) / 16)
    cb(value, [])

    if loop is None:
        return

    # joystick only emits the changes, so it stays eg. 99 if we hold, and doesn't
    # generate new events, repeat the events when it is not 0
    if cc in loop.ctx:
        loop.ctx[cc].cancel()
    if value != 0:
        loop.ctx[cc] = loop.call_later(0.05, check_joy, ev, cc, cb, loop)

def process_midi(seq, ptz, loop):
    evp = snd_seq_event_p()
    if snd_seq_event_input(seq, evp) < 0:
        return

    # deep copy
    ev = type(evp.contents)()
    ctypes.pointer(ev)[0] = evp.contents

    if ev.type == SND_SEQ_EVENT_CONTROLLER:
        check_abs_knob(ev, 71, ptz.do_pan_percent)
        check_abs_knob(ev, 72, ptz.do_tilt_percent)
        check_abs_knob(ev, 73, ptz.do_zoom_percent)

        check_rel_knob(ev, 75, ptz.do_pan_step)
        check_rel_knob(ev, 76, ptz.do_tilt_step)
        check_rel_knob(ev, 77, ptz.do_zoom_step)

        check_rel_knob(ev, 70, ptz.do_pan_speed, loop)
        check_rel_knob(ev, 74, ptz.do_tilt_speed, loop)

        if ptz.has_pantilt_speed:
            check_joy(ev, 78, ptz.do_pan_speed)
            check_joy(ev, 79, ptz.do_tilt_speed)
        elif ptz.has_pantilt_absolute:
            check_joy(ev, 78, ptz.do_pan_step, loop)
            check_joy(ev, 79, ptz.do_tilt_step, loop)

        check_cc(ev, 121, ptz.do_reset)

    elif ev.type == SND_SEQ_EVENT_PGMCHANGE:
        ptz.do_preset(ev.data.control.value + 1, [])
    
    elif ev.type == SND_SEQ_EVENT_PORT_UNSUBSCRIBED:
        logging.error(f'midi port unsubscribed')
        sys.exit(1)

def usage():
    print(f'usage: {sys.argv[0]} [-h] [-l] [-c] [-d DEVICE]\n')
    print(f'optional arguments:')
    print(f'  -h, --help        show this help message and exit')
    print(f'  -l, --list        list midi controllers')
    print(f'  -c, --controller  use controller (client:port), default first')
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
    controller_id = None
    device = '/dev/video0'

    for current_argument, current_value in arguments:
        if current_argument in ('-h', '--help'):
            usage()
            sys.exit(0)
        elif current_argument in ('-l', '--list'):
            list_ctrls = True
        elif current_argument in ('-c', '--controller'):
            controller_id = current_value
        elif current_argument in ('-d', '--device'):
            device = current_value

    seq = snd_seq_p()

    if snd_seq_open(seq, b"default", SND_SEQ_OPEN_INPUT, 0) < 0:
        logging.error("Could not open sequencer")
        sys.exit(2)

    if snd_seq_set_client_name(seq, b"Midi Listener") < 0:
        logging.error("Could not set client name")
        sys.exit(2)

    if snd_seq_create_simple_port(seq, b"listen:in",
                SND_SEQ_PORT_CAP_WRITE|SND_SEQ_PORT_CAP_SUBS_WRITE,
                SND_SEQ_PORT_TYPE_APPLICATION) < 0:
        logging.error("Could not open port")
        sys.exit(2)

    ports = get_hw_client_ports(seq)
    if not ports:
        logging.error("Couldn't find hw devices")
        sys.exit(2)

    if list_ctrls:
        for p in ports:
            print(f'{p[0]}:{p[1]}:{p[2]}')
        sys.exit(0)

    client, port = ports[0][1], ports[0][2]

    if controller_id is not None:
        spl = controller_id.split(':')
        if len(spl) < 2:
            logging.error(f'invalid controller id: {controller_id}')
            sys.exit(2)
        client, port = int(spl[-2]), int(spl[-1])
    
    logging.info(f'using port: {client}:{port}')

    snd_seq_set_client_event_filter(seq, SND_SEQ_EVENT_CONTROLLER)
    snd_seq_set_client_event_filter(seq, SND_SEQ_EVENT_PGMCHANGE)
    snd_seq_set_client_event_filter(seq, SND_SEQ_EVENT_PORT_UNSUBSCRIBED)

    if snd_seq_connect_from(seq, 0, client, port) < 0:
        logging.error("Cannot connect from port")
        sys.exit(2)

    npfd = snd_seq_poll_descriptors_count(seq, select.POLLIN)
    pfd = (pollfd * npfd)()
    snd_seq_poll_descriptors(seq, pfd, npfd, select.POLLIN)

    loop = asyncio.new_event_loop()
    loop.ctx = {}

    loop.add_signal_handler(signal.SIGINT, loop.stop)

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

    for i in range(npfd):
        loop.add_reader(pfd[i].fd, process_midi, seq, ptz, loop)

    try:
        loop.run_forever()
    finally:
        loop.close()

if __name__ == '__main__':
    sys.exit(main())
