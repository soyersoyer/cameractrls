#!/usr/bin/env python3

import os, sys, ctypes, ctypes.util, logging, mmap, struct, getopt, select
from fcntl import ioctl
from threading import Thread

from cameractrls import v4l2_capability, v4l2_format, v4l2_requestbuffers, v4l2_buffer
from cameractrls import VIDIOC_QUERYCAP, VIDIOC_G_FMT, VIDIOC_S_FMT, VIDIOC_REQBUFS, VIDIOC_QUERYBUF, VIDIOC_QBUF, VIDIOC_DQBUF, VIDIOC_STREAMON, VIDIOC_STREAMOFF
from cameractrls import V4L2_CAP_VIDEO_CAPTURE, V4L2_CAP_STREAMING, V4L2_MEMORY_MMAP, V4L2_BUF_TYPE_VIDEO_CAPTURE
from cameractrls import V4L2_PIX_FMT_YUYV, V4L2_PIX_FMT_YVYU, V4L2_PIX_FMT_UYVY, V4L2_PIX_FMT_YU12, V4L2_PIX_FMT_YV12
from cameractrls import V4L2_PIX_FMT_NV12, V4L2_PIX_FMT_NV21, V4L2_PIX_FMT_GREY
from cameractrls import V4L2_PIX_FMT_RGB565, V4L2_PIX_FMT_RGB24, V4L2_PIX_FMT_BGR24, V4L2_PIX_FMT_RX24
from cameractrls import V4L2_PIX_FMT_MJPEG, V4L2_PIX_FMT_JPEG

sdl2lib = ctypes.util.find_library('SDL2-2.0')
if sdl2lib == None:
    print('libSDL2 not found, please install the libsdl2-2.0 package!')
    sys.exit(2)
sdl2 = ctypes.CDLL(sdl2lib)

turbojpeglib = ctypes.util.find_library('turbojpeg')
if turbojpeglib == None:
    print('libturbojpeg not found, please install the libturbojpeg package!')
    sys.exit(2)
turbojpeg = ctypes.CDLL(turbojpeglib)

SDL_Init = sdl2.SDL_Init
SDL_Init.restype = ctypes.c_int
SDL_Init.argtypes = [ctypes.c_uint32]
# int SDL_Init(Uint32 flags);

SDL_GetError = sdl2.SDL_GetError
SDL_GetError.restype = ctypes.c_char_p
SDL_GetError.argtypes = []
# const char* SDL_GetError(void);

SDL_RegisterEvents = sdl2.SDL_RegisterEvents
SDL_RegisterEvents.restype = ctypes.c_uint32
SDL_RegisterEvents.argtypes = [ctypes.c_int]
# Uint32 SDL_RegisterEvents(int numevents);

SDL_CreateWindow = sdl2.SDL_CreateWindow
SDL_CreateWindow.restype = ctypes.c_void_p
SDL_CreateWindow.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint32]
# SDL_Window * SDL_CreateWindow(const char *title, int x, int y, int w, int h, Uint32 flags);

SDL_CreateRenderer = sdl2.SDL_CreateRenderer
SDL_CreateRenderer.restype = ctypes.c_void_p
SDL_CreateRenderer.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32]
# SDL_Renderer * SDL_CreateRenderer(SDL_Window * window, int index, Uint32 flags);

SDL_RenderSetLogicalSize = sdl2.SDL_RenderSetLogicalSize
SDL_RenderSetLogicalSize.restype = ctypes.c_int
SDL_RenderSetLogicalSize.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
# int SDL_RenderSetLogicalSize(SDL_Renderer * renderer, int w, int h);

SDL_CreateTexture = sdl2.SDL_CreateTexture
SDL_CreateTexture.restype = ctypes.c_void_p
SDL_CreateTexture.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_int, ctypes.c_int]
# SDL_Texture * SDL_CreateTexture(SDL_Renderer * renderer, Uint32 format, int access, int w, int h);

SDL_UpdateTexture = sdl2.SDL_UpdateTexture
SDL_UpdateTexture.restype = ctypes.c_int
SDL_UpdateTexture.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]
# int SDL_UpdateTexture(SDL_Texture * texture, const SDL_Rect * rect, const void *pixels, int pitch);

SDL_RenderClear = sdl2.SDL_RenderClear
SDL_RenderClear.restype = ctypes.c_int
SDL_RenderClear.argtypes = [ctypes.c_void_p]
# int SDL_RenderClear(SDL_Renderer * renderer);

SDL_RenderCopyEx = sdl2.SDL_RenderCopyEx
SDL_RenderCopyEx.restype = ctypes.c_int
SDL_RenderCopyEx.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_double, ctypes.c_void_p, ctypes.c_int]
#int SDL_RenderCopyEx(SDL_Renderer * renderer, SDL_Texture * texture, const SDL_Rect * srcrect, const SDL_Rect * dstrect,
#                   const double angle, const SDL_Point *center, const SDL_RendererFlip flip);

SDL_RenderPresent = sdl2.SDL_RenderPresent
SDL_RenderPresent.restype = None
SDL_RenderPresent.argtypes = [ctypes.c_void_p]
# void SDL_RenderPresent(SDL_Renderer * renderer);

SDL_PushEvent = sdl2.SDL_PushEvent
SDL_PushEvent.restype = ctypes.c_int
SDL_PushEvent.argtypes = [ctypes.c_void_p]
#int SDL_PushEvent(SDL_Event * event);

SDL_WaitEvent = sdl2.SDL_WaitEvent
SDL_WaitEvent.restype = ctypes.c_int
SDL_WaitEvent.argtypes = [ctypes.c_void_p]
# int SDL_WaitEvent(SDL_Event * event);

SDL_DestroyWindow = sdl2.SDL_DestroyWindow
SDL_DestroyWindow.argtypes = [ctypes.c_void_p]
# void SDL_DestroyWindow(SDL_Window * window);

SDL_Quit = sdl2.SDL_Quit
# void SDL_Quit(void);

SDL_SetWindowFullscreen = sdl2.SDL_SetWindowFullscreen
SDL_SetWindowFullscreen.restype = ctypes.c_int
SDL_SetWindowFullscreen.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
# int SDL_SetWindowFullscreen(SDL_Window * window, Uint32 flags);

SDL_ShowSimpleMessageBox = sdl2.SDL_ShowSimpleMessageBox
SDL_ShowSimpleMessageBox.restype = ctypes.c_int
SDL_ShowSimpleMessageBox.argtypes = [ctypes.c_uint32, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p]
# int SDL_ShowSimpleMessageBox(Uint32 flags, const char *title, const char *message, SDL_Window *window);

SDL_INIT_VIDEO = 0x00000020
SDL_QUIT = 0x100
SDL_KEYDOWN = 0x300
SDL_MOUSEBUTTONUP = 0x402
SDL_BUTTON_LEFT = 1
SDLK_f = ord('f')
SDLK_m = ord('m')
SDLK_q = ord('q')
SDLK_r = ord('r')
SDLK_ESCAPE = 27
KMOD_NONE = 0x0000
KMOD_LSHIFT = 0x0001
KMOD_RSHIFT = 0x0002
KMOD_SHIFT = KMOD_LSHIFT | KMOD_RSHIFT


SDL_WINDOW_FULLSCREEN = 0x00000001
SDL_WINDOW_RESIZABLE = 0x00000020
SDL_WINDOW_FULLSCREEN_DESKTOP = (SDL_WINDOW_FULLSCREEN | 0x00001000)
SDL_WINDOWPOS_UNDEFINED = 0x1FFF0000

SDL_MESSAGEBOX_ERROR = 0x00000010

def SDL_FOURCC(a, b, c, d):
    return (ord(a) << 0) | (ord(b) << 8) | (ord(c) << 16) | (ord(d) << 24)
SDL_PIXELFORMAT_YUY2 = SDL_FOURCC('Y', 'U', 'Y', '2')
SDL_PIXELFORMAT_YV12 = SDL_FOURCC('Y', 'V', '1', '2')
SDL_PIXELFORMAT_YVYU = SDL_FOURCC('Y', 'V', 'Y', 'U')
SDL_PIXELFORMAT_UYVY = SDL_FOURCC('U', 'Y', 'V', 'Y')
SDL_PIXELFORMAT_VYUY = SDL_FOURCC('V', 'Y', 'U', 'Y')
SDL_PIXELFORMAT_NV12 = SDL_FOURCC('N', 'V', '1', '2')
SDL_PIXELFORMAT_NV21 = SDL_FOURCC('N', 'V', '2', '1')
SDL_PIXELFORMAT_IYUV = SDL_FOURCC('I', 'Y', 'U', 'V')
SDL_PIXELFORMAT_RGB24 = 386930691
SDL_PIXELFORMAT_BGR24 = 390076419
SDL_PIXELFORMAT_BGR888 = 374740996 #XBGR8888
SDL_PIXELFORMAT_RGB565 = 353701890
SDL_TEXTUREACCESS_STREAMING = 1

SDL_Keycode = ctypes.c_int32
SDL_Scancode = ctypes.c_int
_event_pad_size = 56 if ctypes.sizeof(ctypes.c_void_p) <= 8 else 64

class SDL_Keysym(ctypes.Structure):
    _fields_ = [
        ('scancode', SDL_Scancode),
        ('sym', SDL_Keycode),
        ('mod', ctypes.c_uint16),
        ('unused', ctypes.c_uint32),
    ]

class SDL_KeyboardEvent(ctypes.Structure):
    _fields_ = [
        ('type', ctypes.c_uint32),
        ('timestamp', ctypes.c_uint32),
        ('windowID', ctypes.c_uint32),
        ('state', ctypes.c_uint8),
        ('repeat', ctypes.c_uint8),
        ('padding2', ctypes.c_uint8),
        ('padding3', ctypes.c_uint8),
        ('keysym', SDL_Keysym),
    ]

class SDL_MouseButtonEvent(ctypes.Structure):
    _fields_ = [
        ('type', ctypes.c_uint32),
        ('timestamp', ctypes.c_uint32),
        ('windowID', ctypes.c_uint32),
        ('which', ctypes.c_uint32),
        ('button', ctypes.c_uint8),
        ('state', ctypes.c_uint8),
        ('clicks', ctypes.c_uint8),
        ('padding1', ctypes.c_uint8),
        ('x', ctypes.c_int32),
        ('y', ctypes.c_int32),
    ]

class SDL_UserEvent(ctypes.Structure):
    _fields_ = [
        ('type', ctypes.c_uint32),
        ('timestamp', ctypes.c_uint32),
        ('windowID', ctypes.c_uint32),
        ('code', ctypes.c_int32),
        ('data1', ctypes.c_void_p),
        ('data2', ctypes.c_void_p),
    ]


class SDL_Event(ctypes.Union):
    _fields_ = [
        ('type', ctypes.c_uint32),
        ('key', SDL_KeyboardEvent),
        ('button', SDL_MouseButtonEvent),
        ('user', SDL_UserEvent),
        ('padding', (ctypes.c_uint8 * _event_pad_size)),
    ]

tj_init_decompress = turbojpeg.tjInitDecompress
tj_init_decompress.restype = ctypes.c_void_p
#tjhandle tjInitDecompress()

tj_decompress = turbojpeg.tjDecompress2
tj_decompress.argtypes = [ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_ubyte), ctypes.c_ulong,
    ctypes.POINTER(ctypes.c_ubyte),
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_int]
tj_decompress.restype = ctypes.c_int
#int tjDecompress2(tjhandle handle,
#                  const unsigned char *jpegBuf, unsigned long jpegSize,
#                  unsigned char *dstBuf,
#                  int width, int pitch, int height, int pixelFormat,
#                  int flags);

tj_get_error_str = turbojpeg.tjGetErrorStr
tj_get_error_str.restype = ctypes.c_char_p
#char* tjGetErrorStr()

tj_destroy = turbojpeg.tjDestroy
tj_destroy.argtypes = [ctypes.c_void_p]
tj_destroy.restype = ctypes.c_int
# int tjDestroy(tjhandle handle);

TJPF_RGB = 0

class V4L2Camera(Thread):
    def __init__(self, device):
        super().__init__()
        self.device = device
        self.width = 0
        self.height = 0
        self.pixelformat = 0
        self.bytesperline = 0
        self.stopped = False
        self.pipe = None
        self.num_cap_bufs = 6
        self.cap_bufs = []

        self.fd = os.open(self.device, os.O_RDWR, 0)

        self.init_device()
        self.init_buffers()


    def init_device(self):
        cap = v4l2_capability()
        fmt = v4l2_format()
        fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE

        ioctl(self.fd, VIDIOC_QUERYCAP, cap)
        ioctl(self.fd, VIDIOC_G_FMT, fmt)

        # some camera need an S_FMT to work
        try:
            ioctl(self.fd, VIDIOC_S_FMT, fmt)
        except Exception as e:
            logging.warning(f'V4L2FmtCtrls: Can\'t set fmt {e}')

        if not (cap.capabilities & V4L2_CAP_VIDEO_CAPTURE):
            logging.error(f'{self.device} is not a video capture device')
            sys.exit(3)

        if not (cap.capabilities & V4L2_CAP_STREAMING):
            logging.error(f'{self.device} does not support streaming i/o')
            sys.exit(3)

        self.width = fmt.fmt.pix.width
        self.height = fmt.fmt.pix.height
        self.pixelformat = fmt.fmt.pix.pixelformat
        self.bytesperline = fmt.fmt.pix.bytesperline


    def init_buffers(self):
        req = v4l2_requestbuffers()

        req.count = self.num_cap_bufs
        req.type = V4L2_BUF_TYPE_VIDEO_CAPTURE
        req.memory = V4L2_MEMORY_MMAP


        try:
            ioctl(self.fd, VIDIOC_REQBUFS, req)
        except Exception as e:
            logging.error(f'Video buffer request failed on {self.device} ({e})')
            sys.exit(3)

        if req.count != self.num_cap_bufs:
            logging.error(f'Insufficient buffer memory on {self.device}')
            sys.exit(3)

        for i in range(req.count):
            buf = v4l2_buffer()
            buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE
            buf.memory = req.memory
            buf.index = i

            ioctl(self.fd, VIDIOC_QUERYBUF, buf)

            if req.memory == V4L2_MEMORY_MMAP:
                buf.buffer = mmap.mmap(self.fd, buf.length,
                    flags=mmap.MAP_SHARED | 0x08000, #MAP_POPULATE
                    prot=mmap.PROT_READ | mmap.PROT_WRITE,
                    offset=buf.m.offset)

            self.cap_bufs.append(buf)

    def capture_loop(self):
        for buf in self.cap_bufs:
            ioctl(self.fd, VIDIOC_QBUF, buf)

        qbuf = v4l2_buffer()
        qbuf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE
        qbuf.memory = self.cap_bufs[0].memory

        poll = select.poll()
        poll.register(self.fd, select.POLLIN)

        while not self.stopped:
            # DQBUF can block forever, so poll with 1000 ms timeout before
            if len(poll.poll(1000)) == 0:
                logging.warning(f'{self.device}: timeout occured')
                continue
            
            ioctl(self.fd, VIDIOC_DQBUF, qbuf)

            buf = self.cap_bufs[qbuf.index]
            buf.bytesused = qbuf.bytesused
            buf.timestamp = qbuf.timestamp

            self.pipe.write_buf(buf)

            ioctl(self.fd, VIDIOC_QBUF, buf)


    def start_capturing(self):
        ioctl(self.fd, VIDIOC_STREAMON, struct.pack('I', V4L2_BUF_TYPE_VIDEO_CAPTURE))
        self.capture_loop()
        ioctl(self.fd, VIDIOC_STREAMOFF, struct.pack('I', V4L2_BUF_TYPE_VIDEO_CAPTURE))

    def stop_capturing(self):
        self.stopped = True

    # thread start
    def run(self):
        self.start_capturing()
    
    # thread stop
    def stop(self):
        self.stop_capturing()
        self.join()


def V4L2Format2SDL(format):
    if format == V4L2_PIX_FMT_YUYV:
        return SDL_PIXELFORMAT_YUY2
    elif format == V4L2_PIX_FMT_YVYU:
        return SDL_PIXELFORMAT_YVYU
    elif format == V4L2_PIX_FMT_UYVY:
        return SDL_PIXELFORMAT_UYVY
    elif format == V4L2_PIX_FMT_NV12:
        return SDL_PIXELFORMAT_NV12
    elif format == V4L2_PIX_FMT_NV21:
        return SDL_PIXELFORMAT_NV21
    elif format == V4L2_PIX_FMT_YU12:
        return SDL_PIXELFORMAT_IYUV
    elif format == V4L2_PIX_FMT_YV12:
        return SDL_PIXELFORMAT_YV12
    elif format == V4L2_PIX_FMT_RGB565:
        return SDL_PIXELFORMAT_RGB565
    elif format == V4L2_PIX_FMT_RGB24:
        return SDL_PIXELFORMAT_RGB24
    elif format == V4L2_PIX_FMT_BGR24:
        return SDL_PIXELFORMAT_BGR24
    elif format == V4L2_PIX_FMT_RX24:
        return SDL_PIXELFORMAT_BGR888
    elif format in [V4L2_PIX_FMT_MJPEG, V4L2_PIX_FMT_JPEG]:
        return SDL_PIXELFORMAT_RGB24
    elif format == V4L2_PIX_FMT_GREY:
        return SDL_PIXELFORMAT_NV12

    formats = 'Sorry, only YUYV, YVYU, UYVY, NV12, NV21, YU12, RGBP, RGB3, BGR3, RX24, MJPG, JPEG, GREY are supported yet.'
    logging.error(f'Invalid pixel format: {formats}')
    SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, b'Invalid pixel format', bytes(formats, 'utf-8'), None)
    sys.exit(3)

class SDLCameraWindow():
    def __init__(self, device, angle, flip):
        self.cam = V4L2Camera(device)
        self.cam.pipe = self
        width = self.cam.width
        height = self.cam.height

        self.fullscreen = False
        self.tj = None
        self.outbuffer = None
        self.bytesperline = self.cam.bytesperline

        self.angle = angle
        self.flip = flip

        if self.cam.pixelformat in [V4L2_PIX_FMT_MJPEG, V4L2_PIX_FMT_JPEG]:
            self.tj = tj_init_decompress()
            # create rgb buffer
            buf_size = width * height * 3
            buf = ctypes.create_string_buffer(b"", buf_size)
            self.outbuffer = (ctypes.c_uint8 * buf_size).from_buffer(buf)
            self.bytesperline = width * 3
        elif self.cam.pixelformat == V4L2_PIX_FMT_GREY:
            # create nv12 buffer
            buf_size = width * height * 2
            buf = ctypes.create_string_buffer(b"", buf_size)
            self.outbuffer = (ctypes.c_uint8 * buf_size).from_buffer(buf)
            ctypes.memset(self.outbuffer, 128, buf_size) # 128 = cb cr midpoint

        if SDL_Init(SDL_INIT_VIDEO) != 0:
            logging.error(f'SDL_Init failed: {SDL_GetError()}')
            sys.exit(1)

        # create a new sdl user event type for new image events
        self.sdl_new_image_event = SDL_RegisterEvents(1)
        # new image event
        self.new_image_event = SDL_Event()
        self.new_image_event.type = self.sdl_new_image_event

        self.window = SDL_CreateWindow(bytes(device, 'utf-8'), SDL_WINDOWPOS_UNDEFINED, SDL_WINDOWPOS_UNDEFINED, width, height, SDL_WINDOW_RESIZABLE)
        if self.window == None:
            logging.error(f'SDL_CreateWindow failed: {SDL_GetError()}')
            sys.exit(1)
        self.renderer = SDL_CreateRenderer(self.window, -1, 0)
        if self.renderer == None:
            logging.error(f'SDL_CreateRenderer failed: {SDL_GetError()}')
            sys.exit(1)
        if SDL_RenderSetLogicalSize(self.renderer, width, height) != 0:
            logging.warning(f'SDL_RenderSetlogicalSize failed: {SDL_GetError()}')
        self.texture = SDL_CreateTexture(self.renderer, V4L2Format2SDL(self.cam.pixelformat), SDL_TEXTUREACCESS_STREAMING, width, height)
        if self.texture == None:
            logging.error(f'SDL_CreateTexture failed: {SDL_GetError()}')
            sys.exit(1)

    def write_buf(self, buf):
        ptr = (ctypes.c_uint8 * buf.bytesused).from_buffer(buf.buffer)
        if self.cam.pixelformat == V4L2_PIX_FMT_MJPEG or self.cam.pixelformat == V4L2_PIX_FMT_JPEG:
            if tj_decompress(self.tj, ptr, buf.bytesused, self.outbuffer, self.cam.width, self.bytesperline, self.cam.height, TJPF_RGB, 0) != 0:
                logging.warning(f'tj_decompress failed: {tj_get_error_str()}')
                return
            ptr = self.outbuffer
        elif self.cam.pixelformat == V4L2_PIX_FMT_GREY:
            ctypes.memmove(self.outbuffer, ptr, buf.bytesused)
            ptr = self.outbuffer

        self.new_image_event.user.data1 = ctypes.cast(ptr, ctypes.c_void_p)
        if SDL_PushEvent(ctypes.byref(self.new_image_event)) < 0:
            logging.warning(f'SDL_PushEvent failed: {SDL_GetError()}')

    def event_loop(self):
        event = SDL_Event()
        while SDL_WaitEvent(ctypes.byref(event)) != 0:
            if event.type == SDL_QUIT:
                self.stop_capturing()
                break
            elif event.type == SDL_KEYDOWN and event.key.repeat == 0:
                if event.key.keysym.sym == SDLK_q or event.key.keysym.sym == SDLK_ESCAPE:
                    self.stop_capturing()
                    break
                if event.key.keysym.sym == SDLK_f:
                    self.toggle_fullscreen()
                elif event.key.keysym.sym == SDLK_r and event.key.keysym.mod == KMOD_NONE:
                    self.rotate(90)
                elif event.key.keysym.sym == SDLK_r and event.key.keysym.mod | KMOD_SHIFT:
                    self.rotate(-90)
                elif event.key.keysym.sym == SDLK_m and event.key.keysym.mod == KMOD_NONE:
                    self.mirror(1)
                elif event.key.keysym.sym == SDLK_m and event.key.keysym.mod | KMOD_SHIFT:
                    self.mirror(-1)
            elif event.type == SDL_MOUSEBUTTONUP and \
                event.button.button == SDL_BUTTON_LEFT and \
                event.button.clicks == 2:
                    self.toggle_fullscreen()
            elif event.type == self.sdl_new_image_event:
                if SDL_UpdateTexture(self.texture, None, event.user.data1, self.bytesperline) != 0:
                    logging.warning(f'SDL_UpdateTexture failed: {SDL_GetError()}')
                if SDL_RenderClear(self.renderer) != 0:
                    logging.warning(f'SDL_RenderClear failed: {SDL_GetError()}')
                if SDL_RenderCopyEx(self.renderer, self.texture, None, None, self.angle, None, self.flip) != 0:
                    logging.warning(f'SDL_RenderCopy failed: {SDL_GetError()}')
                SDL_RenderPresent(self.renderer)

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        SDL_SetWindowFullscreen(self.window, SDL_WINDOW_FULLSCREEN_DESKTOP if self.fullscreen else 0)

    def rotate(self, angle):
        self.angle += angle
        self.angle %= 360

    def mirror(self, flip):
        self.flip += flip
        self.flip %= 4

    def start_capturing(self):
        self.cam.start()
        self.event_loop()

    def stop_capturing(self):
        self.cam.stop()

    def close(self):
        tj_destroy(self.tj)
        SDL_DestroyWindow(self.window)
        SDL_Quit()


def usage():
    print(f'usage: {sys.argv[0]} [--help] [-d DEVICE] [-r ANGLE] [-m FLIP]\n')
    print(f'optional arguments:')
    print(f'  -h, --help         show this help message and exit')
    print(f'  -d DEVICE          use DEVICE, default /dev/video0')
    print(f'  -r ANGLE           rotate the image by ANGLE, default 0')
    print(f'  -m FLIP            mirror the image by FLIP, default no, (no, h, v, hv)')
    print()
    print(f'example:')
    print(f'  {sys.argv[0]} -d /dev/video2')
    print()
    print(f'shortcuts:')
    print(f'  f: toggle fullscreen')
    print(f'  r: ANGLE +90 (shift+r -90)')
    print(f'  m: FLIP next (shift+m prev)')


def main():
    try:
        arguments, values = getopt.getopt(sys.argv[1:], 'hd:r:m:', ['help'])
    except getopt.error as err:
        print(err)
        usage()
        sys.exit(2)

    device = '/dev/video0'
    angle = 0
    flip = 0

    for current_argument, current_value in arguments:
        if current_argument in ('-h', '--help'):
            usage()
            sys.exit(0)
        elif current_argument == '-d':
            device = current_value
        elif current_argument == '-r':
            angle = int(current_value)
        elif current_argument == '-m':
            if current_value == 'no':
                flip = 0
            elif current_value == 'h':
                flip = 1
            elif current_value == 'v':
                flip = 2
            elif current_value == 'hv':
                flip = 3
            else:
                print(f'invalid FLIP value: {current_value}')
                usage()
                sys.exit(1)


    os.environ['SDL_VIDEO_X11_WMCLASS'] = 'hu.irl.cameractrls'

    win = SDLCameraWindow(device, angle, flip)
    win.start_capturing()
    win.close()


if __name__ == '__main__':
    main()
