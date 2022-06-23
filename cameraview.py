#!/usr/bin/env python3

import os, sys, ctypes, ctypes.util, logging, mmap, struct, getopt
from fcntl import ioctl

from cameractrls import v4l2_capability, v4l2_format, v4l2_requestbuffers, v4l2_buffer
from cameractrls import VIDIOC_QUERYCAP, VIDIOC_G_FMT, VIDIOC_REQBUFS, VIDIOC_QUERYBUF, VIDIOC_QBUF, VIDIOC_DQBUF, VIDIOC_STREAMON, VIDIOC_STREAMOFF
from cameractrls import V4L2_CAP_VIDEO_CAPTURE, V4L2_CAP_STREAMING, V4L2_MEMORY_MMAP, V4L2_BUF_TYPE_VIDEO_CAPTURE
from cameractrls import V4L2_PIX_FMT_YUYV, V4L2_PIX_FMT_NV12, V4L2_PIX_FMT_MJPEG, V4L2_PIX_FMT_JPEG

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

SDL_CreateWindow = sdl2.SDL_CreateWindow
SDL_CreateWindow.restype = ctypes.c_void_p
SDL_CreateWindow.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint32]
# SDL_Window * SDL_CreateWindow(const char *title, int x, int y, int w, int h, Uint32 flags);

SDL_CreateRenderer = sdl2.SDL_CreateRenderer
SDL_CreateRenderer.restype = ctypes.c_void_p
SDL_CreateRenderer.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32]
# SDL_Renderer * SDL_CreateRenderer(SDL_Window * window, int index, Uint32 flags);

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

SDL_RenderCopy = sdl2.SDL_RenderCopy
SDL_RenderCopy.restype = ctypes.c_int
SDL_RenderCopy.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
# int SDL_RenderCopy(SDL_Renderer * renderer, SDL_Texture * texture, const SDL_Rect * srcrect, const SDL_Rect * dstrect);

SDL_RenderPresent = sdl2.SDL_RenderPresent
SDL_RenderPresent.argtypes = [ctypes.c_void_p]
# void SDL_RenderPresent(SDL_Renderer * renderer);

SDL_PollEvent = sdl2.SDL_PollEvent
SDL_PollEvent.restype = ctypes.c_int
SDL_PollEvent.argtypes = [ctypes.c_void_p]
# int SDL_PollEvent(SDL_Event * event);

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
SDLK_f = ord('f')
SDLK_q = ord('q')

SDL_WINDOW_FULLSCREEN = 0x00000001
SDL_WINDOW_SHOWN = 0x00000004
SDL_WINDOW_FULLSCREEN_DESKTOP = (SDL_WINDOW_FULLSCREEN | 0x00001000)
SDL_WINDOWPOS_UNDEFINED = 0x1FFF0000

SDL_MESSAGEBOX_ERROR = 0x00000010

def SDL_FOURCC(a, b, c, d):
    return (ord(a) << 0) | (ord(b) << 8) | (ord(c) << 16) | (ord(d) << 24)
SDL_PIXELFORMAT_YUY2 = SDL_FOURCC('Y', 'U', 'Y', '2')
SDL_PIXELFORMAT_NV12 = SDL_FOURCC('N', 'V', '1', '2')
SDL_PIXELFORMAT_RGB24 = 386930691
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

class SDL_Event(ctypes.Union):
    _fields_ = [
        ('type', ctypes.c_uint32),
        ('key', SDL_KeyboardEvent),
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

tj_destroy = turbojpeg.tjDestroy
tj_destroy.argtypes = [ctypes.c_void_p]
tj_destroy.restype = ctypes.c_int
# int tjDestroy(tjhandle handle);

TJPF_RGB = 0

class V4L2Camera():
    def __init__(self, device):
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

        while not self.stopped:
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


def V4L2Format2SDL(format):
    if format == V4L2_PIX_FMT_YUYV:
        return SDL_PIXELFORMAT_YUY2
    elif format == V4L2_PIX_FMT_NV12:
        return SDL_PIXELFORMAT_NV12
    elif format in [V4L2_PIX_FMT_MJPEG, V4L2_PIX_FMT_JPEG]:
        return SDL_PIXELFORMAT_RGB24
    logging.error(f'Invalid pixel format: Sorry, only YUYV, NV12, MJPG, JPEG are supported yet.')
    SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, b'Invalid pixel format', b'Sorry, only YUYV, NV12, MJPG, JPEG are supported yet.', None)
    sys.exit(3)

class SDLCameraWindow():
    def __init__(self, device):
        self.cam = V4L2Camera(device)
        self.cam.pipe = self
        width = self.cam.width
        height = self.cam.height

        self.fullscreen = False
        self.tj = None
        self.tjbuffer = None
        
        if self.cam.pixelformat in [V4L2_PIX_FMT_MJPEG, V4L2_PIX_FMT_JPEG]:
            self.tj = tj_init_decompress()

            buf_size = width * height * 3
            buf = ctypes.create_string_buffer(b"", buf_size)
            self.tjbuffer = (ctypes.c_uint8 * buf_size).from_buffer(buf)


        if SDL_Init(SDL_INIT_VIDEO) != 0:
            logging.error(f'SDL_Init failed: {SDL_GetError()}')
            sys.exit(1)

        self.window = SDL_CreateWindow(bytes(device, 'utf-8'), SDL_WINDOWPOS_UNDEFINED, SDL_WINDOWPOS_UNDEFINED, width, height, SDL_WINDOW_SHOWN)
        if self.window == None:
            logging.error(f'SDL_CreateWindow failed: {SDL_GetError()}')
            sys.exit(1)
        self.renderer = SDL_CreateRenderer(self.window, -1, 0)
        if self.renderer == None:
            logging.error(f'SDL_CreateRenderer failed: {SDL_GetError()}')
            sys.exit(1)
        self.texture = SDL_CreateTexture(self.renderer, V4L2Format2SDL(self.cam.pixelformat), SDL_TEXTUREACCESS_STREAMING, width, height)
        if self.texture == None:
            logging.error(f'SDL_CreateTexture failed: {SDL_GetError()}')
            sys.exit(1)
        self.event = SDL_Event()

    def write_buf(self, buf):
        ptr = (ctypes.c_uint8 * buf.bytesused).from_buffer(buf.buffer)
        bytesperline = self.cam.bytesperline
        if self.cam.pixelformat == V4L2_PIX_FMT_MJPEG or self.cam.pixelformat == V4L2_PIX_FMT_JPEG:
            bytesperline = self.cam.width * 3
            tj_decompress(self.tj, ptr, buf.bytesused, self.tjbuffer, self.cam.width, bytesperline, self.cam.height, TJPF_RGB, 0)
            ptr = self.tjbuffer

        SDL_UpdateTexture(self.texture, None, ptr, bytesperline)
        SDL_RenderClear(self.renderer)
        SDL_RenderCopy(self.renderer, self.texture, None, None)
        SDL_RenderPresent(self.renderer)

        while SDL_PollEvent(ctypes.byref(self.event)) != 0:
            if self.event.type == SDL_QUIT:
                self.stop_capturing()
                break
            if self.event.type == SDL_KEYDOWN and self.event.key.repeat == 0:
                if self.event.key.keysym.sym == SDLK_q:
                    self.stop_capturing()
                    break
                if self.event.key.keysym.sym == SDLK_f:
                    self.fullscreen = not self.fullscreen
                    SDL_SetWindowFullscreen(self.window, SDL_WINDOW_FULLSCREEN_DESKTOP if self.fullscreen else 0)

    def start_capturing(self):
        self.cam.start_capturing()

    def stop_capturing(self):
        self.cam.stop_capturing()

    def close(self):
        tj_destroy(self.tj)
        SDL_DestroyWindow(self.window)
        SDL_Quit()


def usage():
    print(f'usage: {sys.argv[0]} [--help] [-d DEVICE]\n')
    print(f'optional arguments:')
    print(f'  -h, --help         show this help message and exit')
    print(f'  -d DEVICE          use DEVICE, default /dev/video0')
    print()
    print(f'example:')
    print(f'  {sys.argv[0]} -d /dev/video2')


def main():
    try:
        arguments, values = getopt.getopt(sys.argv[1:], 'hd:', ['help'])
    except getopt.error as err:
        print(err)
        usage()
        sys.exit(2)

    device = '/dev/video0'

    for current_argument, current_value in arguments:
        if current_argument in ('-h', '--help'):
            usage()
            sys.exit(0)
        elif current_argument in ('-d', '--device'):
            device = current_value


    win = SDLCameraWindow(device)
    win.start_capturing()
    win.close()


if __name__ == '__main__':
    main()
