#!/usr/bin/env python3

import os, sys, ctypes, ctypes.util, logging, mmap, struct, getopt, select
from fcntl import ioctl
from threading import Thread
from operator import lt, gt

from cameractrls import CameraCtrls, PTZController
from cameractrls import v4l2_capability, v4l2_format, v4l2_streamparm, v4l2_requestbuffers, v4l2_buffer
from cameractrls import VIDIOC_QUERYCAP, VIDIOC_G_FMT, VIDIOC_G_PARM, VIDIOC_S_PARM
from cameractrls import VIDIOC_REQBUFS, VIDIOC_QUERYBUF, VIDIOC_QBUF, VIDIOC_DQBUF, VIDIOC_STREAMON, VIDIOC_STREAMOFF
from cameractrls import V4L2_CAP_VIDEO_CAPTURE, V4L2_CAP_STREAMING, V4L2_MEMORY_MMAP, V4L2_BUF_TYPE_VIDEO_CAPTURE
from cameractrls import V4L2_PIX_FMT_YUYV, V4L2_PIX_FMT_YVYU, V4L2_PIX_FMT_UYVY, V4L2_PIX_FMT_YU12, V4L2_PIX_FMT_YV12
from cameractrls import V4L2_PIX_FMT_NV12, V4L2_PIX_FMT_NV21, V4L2_PIX_FMT_GREY
from cameractrls import V4L2_PIX_FMT_RGB565, V4L2_PIX_FMT_RGB24, V4L2_PIX_FMT_BGR24, V4L2_PIX_FMT_RX24
from cameractrls import V4L2_PIX_FMT_MJPEG, V4L2_PIX_FMT_JPEG

sdl2lib = ctypes.util.find_library('SDL2-2.0')
if sdl2lib is None:
    print('libSDL2 not found, please install the libsdl2-2.0 package!')
    sys.exit(2)
sdl2 = ctypes.CDLL(sdl2lib)

turbojpeglib = ctypes.util.find_library('turbojpeg')
if turbojpeglib is None:
    print('libturbojpeg not found, please install the libturbojpeg package!')
    sys.exit(2)
turbojpeg = ctypes.CDLL(turbojpeglib)

class SDL_PixelFormat(ctypes.Structure):
    _fields_ = [
        ('format', ctypes.c_uint32),
        ('palette', ctypes.c_void_p),
    ]

class SDL_Surface(ctypes.Structure):
    _fields_ = [
        ('flags', ctypes.c_uint32),
        ('format', ctypes.POINTER(SDL_PixelFormat)),
        ('w', ctypes.c_int),
        ('h', ctypes.c_int),
        ('pitch', ctypes.c_int),
        ('pixels', ctypes.c_void_p),
    ]

class SDL_Rect(ctypes.Structure):
    _fields_ = [
        ('x', ctypes.c_int),
        ('y', ctypes.c_int),
        ('w', ctypes.c_int),
        ('h', ctypes.c_int),
    ]

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

SDL_RenderGetLogicalSize = sdl2.SDL_RenderGetLogicalSize
SDL_RenderGetLogicalSize.restype = None
SDL_RenderGetLogicalSize.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
# void SDL_RenderGetLogicalSize(SDL_Renderer * renderer, int *w, int *h);

SDL_RenderSetLogicalSize = sdl2.SDL_RenderSetLogicalSize
SDL_RenderSetLogicalSize.restype = ctypes.c_int
SDL_RenderSetLogicalSize.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
# int SDL_RenderSetLogicalSize(SDL_Renderer * renderer, int w, int h);

SDL_GetWindowSize = sdl2.SDL_GetWindowSize
SDL_GetWindowSize.restype = None
SDL_GetWindowSize.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
#void SDL_GetWindowSize(SDL_Window * window, int *w, int *h);

SDL_SetWindowSize = sdl2.SDL_SetWindowSize
SDL_SetWindowSize.restype = None
SDL_SetWindowSize.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
#void SDL_SetWindowSize(SDL_Window * window, int w, int h);

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
SDL_RenderCopyEx.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(SDL_Rect), ctypes.POINTER(SDL_Rect), ctypes.c_double, ctypes.c_void_p, ctypes.c_int]
#int SDL_RenderCopyEx(SDL_Renderer * renderer, SDL_Texture * texture, const SDL_Rect * srcrect, const SDL_Rect * dstrect,
#                   const double angle, const SDL_Point *center, const SDL_RendererFlip flip);

SDL_CreateRGBSurfaceFrom = sdl2.SDL_CreateRGBSurfaceFrom
SDL_CreateRGBSurfaceFrom.restype = ctypes.POINTER(SDL_Surface)
SDL_CreateRGBSurfaceFrom.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                     ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32]
#SDL_Surface* SDL_CreateRGBSurfaceFrom(void *pixels, int width, int height, int depth, int pitch,
# Uint32 Rmask, Uint32 Gmask, Uint32 Bmask, Uint32 Amask);

SDL_ConvertPixels = sdl2.SDL_ConvertPixels
SDL_ConvertPixels.restype = ctypes.c_int
SDL_ConvertPixels.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_int]
#int SDL_ConvertPixels(int width, int height,
#                      Uint32 src_format,
#                      const void * src, int src_pitch,
#                      Uint32 dst_format,
#                      void * dst, int dst_pitch);

SDL_SetPaletteColors = sdl2.SDL_SetPaletteColors
SDL_SetPaletteColors.restype = ctypes.c_int
SDL_SetPaletteColors.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
#int SDL_SetPaletteColors(SDL_Palette * palette, const SDL_Color * colors, int firstcolor, int ncolors);

SDL_CreateTextureFromSurface = sdl2.SDL_CreateTextureFromSurface
SDL_CreateTextureFromSurface.restype = ctypes.c_void_p
SDL_CreateTextureFromSurface.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
#SDL_Texture* SDL_CreateTextureFromSurface(SDL_Renderer * renderer, SDL_Surface * surface);

SDL_DestroyTexture = sdl2.SDL_DestroyTexture
SDL_DestroyTexture.restype = None
SDL_DestroyTexture.argtypes = [ctypes.c_void_p]
#void SDL_DestroyTexture(SDL_Texture * texture);

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
SDL_KEYUP = 0x301
SDL_MOUSEBUTTONUP = 0x402
SDL_BUTTON_LEFT = 1
SDLK_1 = ord('1')
SDLK_2 = ord('2')
SDLK_3 = ord('3')
SDLK_4 = ord('4')
SDLK_5 = ord('5')
SDLK_6 = ord('6')
SDLK_7 = ord('7')
SDLK_8 = ord('8')
SDLK_c = ord('c')
SDLK_f = ord('f')
SDLK_m = ord('m')
SDLK_q = ord('q')
SDLK_r = ord('r')
SDLK_w = ord('w')
SDLK_a = ord('a')
SDLK_s = ord('s')
SDLK_d = ord('d')
SDLK_PLUS = ord('+')
SDLK_MINUS = ord('-')
SDLK_ESCAPE = 27
SDLK_SCANCODE_MASK = 1<<30

SDLK_HOME = 74 | SDLK_SCANCODE_MASK
SDLK_PAGEUP = 75 | SDLK_SCANCODE_MASK
SDLK_END = 77 | SDLK_SCANCODE_MASK
SDLK_PAGEDOWN = 78 | SDLK_SCANCODE_MASK
SDLK_RIGHT = 79 | SDLK_SCANCODE_MASK
SDLK_LEFT = 80 | SDLK_SCANCODE_MASK
SDLK_DOWN = 81 | SDLK_SCANCODE_MASK
SDLK_UP = 82 | SDLK_SCANCODE_MASK
SDLK_KP_MINUS = 86 | SDLK_SCANCODE_MASK
SDLK_KP_PLUS = 87 | SDLK_SCANCODE_MASK
SDLK_KP_1 = 89 | SDLK_SCANCODE_MASK
SDLK_KP_2 = 90 | SDLK_SCANCODE_MASK
SDLK_KP_3 = 91 | SDLK_SCANCODE_MASK
SDLK_KP_4 = 92 | SDLK_SCANCODE_MASK
SDLK_KP_5 = 93 | SDLK_SCANCODE_MASK
SDLK_KP_6 = 94 | SDLK_SCANCODE_MASK
SDLK_KP_7 = 95 | SDLK_SCANCODE_MASK
SDLK_KP_8 = 96 | SDLK_SCANCODE_MASK
SDLK_KP_9 = 97 | SDLK_SCANCODE_MASK
SDLK_KP_0 = 98 | SDLK_SCANCODE_MASK

KMOD_NONE = 0x0000
KMOD_LSHIFT = 0x0001
KMOD_RSHIFT = 0x0002
KMOD_LCTRL = 0x0040
KMOD_RCTRL = 0x0080
KMOD_SHIFT = KMOD_LSHIFT | KMOD_RSHIFT
KMOD_CTRL = KMOD_LCTRL | KMOD_RCTRL


SDL_PAL_GRAYSCALE_L = b'\
\x00\x00\x00\0\x01\x01\x01\0\x02\x02\x02\0\x03\x03\x03\0\x04\x04\x04\0\x05\x05\x05\0\x06\x06\x06\0\x07\x07\x07\0\x08\x08\x08\0\x09\x09\x09\0\x0a\x0a\x0a\0\
\x0b\x0b\x0b\0\x0c\x0c\x0c\0\x0d\x0d\x0d\0\x0e\x0e\x0e\0\x0f\x0f\x0f\0\x10\x10\x10\0\x11\x11\x11\0\x12\x12\x12\0\x13\x13\x13\0\x14\x14\x14\0\x15\x15\x15\0\
\x16\x16\x16\0\x17\x17\x17\0\x18\x18\x18\0\x19\x19\x19\0\x1a\x1a\x1a\0\x1b\x1b\x1b\0\x1c\x1c\x1c\0\x1d\x1d\x1d\0\x1e\x1e\x1e\0\x1f\x1f\x1f\0\x20\x20\x20\0\
\x21\x21\x21\0\x22\x22\x22\0\x23\x23\x23\0\x24\x24\x24\0\x25\x25\x25\0\x26\x26\x26\0\x27\x27\x27\0\x28\x28\x28\0\x29\x29\x29\0\x2a\x2a\x2a\0\x2b\x2b\x2b\0\
\x2c\x2c\x2c\0\x2d\x2d\x2d\0\x2e\x2e\x2e\0\x2f\x2f\x2f\0\x30\x30\x30\0\x31\x31\x31\0\x32\x32\x32\0\x33\x33\x33\0\x34\x34\x34\0\x35\x35\x35\0\x36\x36\x36\0\
\x37\x37\x37\0\x38\x38\x38\0\x39\x39\x39\0\x3a\x3a\x3a\0\x3b\x3b\x3b\0\x3c\x3c\x3c\0\x3d\x3d\x3d\0\x3e\x3e\x3e\0\x3f\x3f\x3f\0\x40\x40\x40\0\x41\x41\x41\0\
\x42\x42\x42\0\x43\x43\x43\0\x44\x44\x44\0\x45\x45\x45\0\x46\x46\x46\0\x47\x47\x47\0\x48\x48\x48\0\x49\x49\x49\0\x4a\x4a\x4a\0\x4b\x4b\x4b\0\x4c\x4c\x4c\0\
\x4d\x4d\x4d\0\x4e\x4e\x4e\0\x4f\x4f\x4f\0\x50\x50\x50\0\x51\x51\x51\0\x52\x52\x52\0\x53\x53\x53\0\x54\x54\x54\0\x55\x55\x55\0\x56\x56\x56\0\x57\x57\x57\0\
\x58\x58\x58\0\x59\x59\x59\0\x5a\x5a\x5a\0\x5b\x5b\x5b\0\x5c\x5c\x5c\0\x5d\x5d\x5d\0\x5e\x5e\x5e\0\x5f\x5f\x5f\0\x60\x60\x60\0\x61\x61\x61\0\x62\x62\x62\0\
\x63\x63\x63\0\x64\x64\x64\0\x65\x65\x65\0\x66\x66\x66\0\x67\x67\x67\0\x68\x68\x68\0\x69\x69\x69\0\x6a\x6a\x6a\0\x6b\x6b\x6b\0\x6c\x6c\x6c\0\x6d\x6d\x6d\0\
\x6e\x6e\x6e\0\x6f\x6f\x6f\0\x70\x70\x70\0\x71\x71\x71\0\x72\x72\x72\0\x73\x73\x73\0\x74\x74\x74\0\x75\x75\x75\0\x76\x76\x76\0\x77\x77\x77\0\x78\x78\x78\0\
\x79\x79\x79\0\x7a\x7a\x7a\0\x7b\x7b\x7b\0\x7c\x7c\x7c\0\x7d\x7d\x7d\0\x7e\x7e\x7e\0\x7f\x7f\x7f\0\x80\x80\x80\0\x81\x81\x81\0\x82\x82\x82\0\x83\x83\x83\0\
\x84\x84\x84\0\x85\x85\x85\0\x86\x86\x86\0\x87\x87\x87\0\x88\x88\x88\0\x89\x89\x89\0\x8a\x8a\x8a\0\x8b\x8b\x8b\0\x8c\x8c\x8c\0\x8d\x8d\x8d\0\x8e\x8e\x8e\0\
\x8f\x8f\x8f\0\x90\x90\x90\0\x91\x91\x91\0\x92\x92\x92\0\x93\x93\x93\0\x94\x94\x94\0\x95\x95\x95\0\x96\x96\x96\0\x97\x97\x97\0\x98\x98\x98\0\x99\x99\x99\0\
\x9a\x9a\x9a\0\x9b\x9b\x9b\0\x9c\x9c\x9c\0\x9d\x9d\x9d\0\x9e\x9e\x9e\0\x9f\x9f\x9f\0\xa0\xa0\xa0\0\xa1\xa1\xa1\0\xa2\xa2\xa2\0\xa3\xa3\xa3\0\xa4\xa4\xa4\0\
\xa5\xa5\xa5\0\xa6\xa6\xa6\0\xa7\xa7\xa7\0\xa8\xa8\xa8\0\xa9\xa9\xa9\0\xaa\xaa\xaa\0\xab\xab\xab\0\xac\xac\xac\0\xad\xad\xad\0\xae\xae\xae\0\xaf\xaf\xaf\0\
\xb0\xb0\xb0\0\xb1\xb1\xb1\0\xb2\xb2\xb2\0\xb3\xb3\xb3\0\xb4\xb4\xb4\0\xb5\xb5\xb5\0\xb6\xb6\xb6\0\xb7\xb7\xb7\0\xb8\xb8\xb8\0\xb9\xb9\xb9\0\xba\xba\xba\0\
\xbb\xbb\xbb\0\xbc\xbc\xbc\0\xbd\xbd\xbd\0\xbe\xbe\xbe\0\xbf\xbf\xbf\0\xc0\xc0\xc0\0\xc1\xc1\xc1\0\xc2\xc2\xc2\0\xc3\xc3\xc3\0\xc4\xc4\xc4\0\xc5\xc5\xc5\0\
\xc6\xc6\xc6\0\xc7\xc7\xc7\0\xc8\xc8\xc8\0\xc9\xc9\xc9\0\xca\xca\xca\0\xcb\xcb\xcb\0\xcc\xcc\xcc\0\xcd\xcd\xcd\0\xce\xce\xce\0\xcf\xcf\xcf\0\xd0\xd0\xd0\0\
\xd1\xd1\xd1\0\xd2\xd2\xd2\0\xd3\xd3\xd3\0\xd4\xd4\xd4\0\xd5\xd5\xd5\0\xd6\xd6\xd6\0\xd7\xd7\xd7\0\xd8\xd8\xd8\0\xd9\xd9\xd9\0\xda\xda\xda\0\xdb\xdb\xdb\0\
\xdc\xdc\xdc\0\xdd\xdd\xdd\0\xde\xde\xde\0\xdf\xdf\xdf\0\xe0\xe0\xe0\0\xe1\xe1\xe1\0\xe2\xe2\xe2\0\xe3\xe3\xe3\0\xe4\xe4\xe4\0\xe5\xe5\xe5\0\xe6\xe6\xe6\0\
\xe7\xe7\xe7\0\xe8\xe8\xe8\0\xe9\xe9\xe9\0\xea\xea\xea\0\xeb\xeb\xeb\0\xec\xec\xec\0\xed\xed\xed\0\xee\xee\xee\0\xef\xef\xef\0\xf0\xf0\xf0\0\xf1\xf1\xf1\0\
\xf2\xf2\xf2\0\xf3\xf3\xf3\0\xf4\xf4\xf4\0\xf5\xf5\xf5\0\xf6\xf6\xf6\0\xf7\xf7\xf7\0\xf8\xf8\xf8\0\xf9\xf9\xf9\0\xfa\xfa\xfa\0\xfb\xfb\xfb\0\xfc\xfc\xfc\0\
\xfd\xfd\xfd\0\xfe\xfe\xfe\0\xff\xff\xff\0'
SDL_PAL_GRAYSCALE = (ctypes.c_uint8 * len(SDL_PAL_GRAYSCALE_L))(*SDL_PAL_GRAYSCALE_L)

# palettes from https://github.com/sciapp/gr/blob/master/lib/gr/cm.h
# print('\\\n'.join(re.findall('.{0,154}', ''.join([f'\\x{hex(x)[2:4]}\\x{hex(x)[4:6]}\\x{hex(x)[6:8]}\\0' for x in pal]))))
SDL_PAL_INFERNO_L = b'\
\x00\x00\x04\0\x01\x00\x05\0\x01\x01\x06\0\x01\x01\x08\0\x02\x01\x0a\0\x02\x02\x0c\0\x02\x02\x0e\0\x03\x02\x10\0\x04\x03\x12\0\x04\x03\x14\0\x05\x04\x17\0\
\x06\x04\x19\0\x07\x05\x1b\0\x08\x05\x1d\0\x09\x06\x1f\0\x0a\x07\x22\0\x0b\x07\x24\0\x0c\x08\x26\0\x0d\x08\x29\0\x0e\x09\x2b\0\x10\x09\x2d\0\x11\x0a\x30\0\
\x12\x0a\x32\0\x14\x0b\x34\0\x15\x0b\x37\0\x16\x0b\x39\0\x18\x0c\x3c\0\x19\x0c\x3e\0\x1b\x0c\x41\0\x1c\x0c\x43\0\x1e\x0c\x45\0\x1f\x0c\x48\0\x21\x0c\x4a\0\
\x23\x0c\x4c\0\x24\x0c\x4f\0\x26\x0c\x51\0\x28\x0b\x53\0\x29\x0b\x55\0\x2b\x0b\x57\0\x2d\x0b\x59\0\x2f\x0a\x5b\0\x31\x0a\x5c\0\x32\x0a\x5e\0\x34\x0a\x5f\0\
\x36\x09\x61\0\x38\x09\x62\0\x39\x09\x63\0\x3b\x09\x64\0\x3d\x09\x65\0\x3e\x09\x66\0\x40\x0a\x67\0\x42\x0a\x68\0\x44\x0a\x68\0\x45\x0a\x69\0\x47\x0b\x6a\0\
\x49\x0b\x6a\0\x4a\x0c\x6b\0\x4c\x0c\x6b\0\x4d\x0d\x6c\0\x4f\x0d\x6c\0\x51\x0e\x6c\0\x52\x0e\x6d\0\x54\x0f\x6d\0\x55\x0f\x6d\0\x57\x10\x6e\0\x59\x10\x6e\0\
\x5a\x11\x6e\0\x5c\x12\x6e\0\x5d\x12\x6e\0\x5f\x13\x6e\0\x61\x13\x6e\0\x62\x14\x6e\0\x64\x15\x6e\0\x65\x15\x6e\0\x67\x16\x6e\0\x69\x16\x6e\0\x6a\x17\x6e\0\
\x6c\x18\x6e\0\x6d\x18\x6e\0\x6f\x19\x6e\0\x71\x19\x6e\0\x72\x1a\x6e\0\x74\x1a\x6e\0\x75\x1b\x6e\0\x77\x1c\x6d\0\x78\x1c\x6d\0\x7a\x1d\x6d\0\x7c\x1d\x6d\0\
\x7d\x1e\x6d\0\x7f\x1e\x6c\0\x80\x1f\x6c\0\x82\x20\x6c\0\x84\x20\x6b\0\x85\x21\x6b\0\x87\x21\x6b\0\x88\x22\x6a\0\x8a\x22\x6a\0\x8c\x23\x69\0\x8d\x23\x69\0\
\x8f\x24\x69\0\x90\x25\x68\0\x92\x25\x68\0\x93\x26\x67\0\x95\x26\x67\0\x97\x27\x66\0\x98\x27\x66\0\x9a\x28\x65\0\x9b\x29\x64\0\x9d\x29\x64\0\x9f\x2a\x63\0\
\xa0\x2a\x63\0\xa2\x2b\x62\0\xa3\x2c\x61\0\xa5\x2c\x60\0\xa6\x2d\x60\0\xa8\x2e\x5f\0\xa9\x2e\x5e\0\xab\x2f\x5e\0\xad\x30\x5d\0\xae\x30\x5c\0\xb0\x31\x5b\0\
\xb1\x32\x5a\0\xb3\x32\x5a\0\xb4\x33\x59\0\xb6\x34\x58\0\xb7\x35\x57\0\xb9\x35\x56\0\xba\x36\x55\0\xbc\x37\x54\0\xbd\x38\x53\0\xbf\x39\x52\0\xc0\x3a\x51\0\
\xc1\x3a\x50\0\xc3\x3b\x4f\0\xc4\x3c\x4e\0\xc6\x3d\x4d\0\xc7\x3e\x4c\0\xc8\x3f\x4b\0\xca\x40\x4a\0\xcb\x41\x49\0\xcc\x42\x48\0\xce\x43\x47\0\xcf\x44\x46\0\
\xd0\x45\x45\0\xd2\x46\x44\0\xd3\x47\x43\0\xd4\x48\x42\0\xd5\x4a\x41\0\xd7\x4b\x3f\0\xd8\x4c\x3e\0\xd9\x4d\x3d\0\xda\x4e\x3c\0\xdb\x50\x3b\0\xdd\x51\x3a\0\
\xde\x52\x38\0\xdf\x53\x37\0\xe0\x55\x36\0\xe1\x56\x35\0\xe2\x57\x34\0\xe3\x59\x33\0\xe4\x5a\x31\0\xe5\x5c\x30\0\xe6\x5d\x2f\0\xe7\x5e\x2e\0\xe8\x60\x2d\0\
\xe9\x61\x2b\0\xea\x63\x2a\0\xeb\x64\x29\0\xeb\x66\x28\0\xec\x67\x26\0\xed\x69\x25\0\xee\x6a\x24\0\xef\x6c\x23\0\xef\x6e\x21\0\xf0\x6f\x20\0\xf1\x71\x1f\0\
\xf1\x73\x1d\0\xf2\x74\x1c\0\xf3\x76\x1b\0\xf3\x78\x19\0\xf4\x79\x18\0\xf5\x7b\x17\0\xf5\x7d\x15\0\xf6\x7e\x14\0\xf6\x80\x13\0\xf7\x82\x12\0\xf7\x84\x10\0\
\xf8\x85\x0f\0\xf8\x87\x0e\0\xf8\x89\x0c\0\xf9\x8b\x0b\0\xf9\x8c\x0a\0\xf9\x8e\x09\0\xfa\x90\x08\0\xfa\x92\x07\0\xfa\x94\x07\0\xfb\x96\x06\0\xfb\x97\x06\0\
\xfb\x99\x06\0\xfb\x9b\x06\0\xfb\x9d\x07\0\xfc\x9f\x07\0\xfc\xa1\x08\0\xfc\xa3\x09\0\xfc\xa5\x0a\0\xfc\xa6\x0c\0\xfc\xa8\x0d\0\xfc\xaa\x0f\0\xfc\xac\x11\0\
\xfc\xae\x12\0\xfc\xb0\x14\0\xfc\xb2\x16\0\xfc\xb4\x18\0\xfb\xb6\x1a\0\xfb\xb8\x1d\0\xfb\xba\x1f\0\xfb\xbc\x21\0\xfb\xbe\x23\0\xfa\xc0\x26\0\xfa\xc2\x28\0\
\xfa\xc4\x2a\0\xfa\xc6\x2d\0\xf9\xc7\x2f\0\xf9\xc9\x32\0\xf9\xcb\x35\0\xf8\xcd\x37\0\xf8\xcf\x3a\0\xf7\xd1\x3d\0\xf7\xd3\x40\0\xf6\xd5\x43\0\xf6\xd7\x46\0\
\xf5\xd9\x49\0\xf5\xdb\x4c\0\xf4\xdd\x4f\0\xf4\xdf\x53\0\xf4\xe1\x56\0\xf3\xe3\x5a\0\xf3\xe5\x5d\0\xf2\xe6\x61\0\xf2\xe8\x65\0\xf2\xea\x69\0\xf1\xec\x6d\0\
\xf1\xed\x71\0\xf1\xef\x75\0\xf1\xf1\x79\0\xf2\xf2\x7d\0\xf2\xf4\x82\0\xf3\xf5\x86\0\xf3\xf6\x8a\0\xf4\xf8\x8e\0\xf5\xf9\x92\0\xf6\xfa\x96\0\xf8\xfb\x9a\0\
\xf9\xfc\x9d\0\xfa\xfd\xa1\0\xfc\xff\xa4\0'
SDL_PAL_INFERNO = (ctypes.c_uint8 * len(SDL_PAL_INFERNO_L))(*SDL_PAL_INFERNO_L)

SDL_PAL_VIRIDIS_L = b'\
\x44\x01\x54\0\x44\x02\x56\0\x45\x04\x57\0\x45\x05\x59\0\x46\x07\x5a\0\x46\x08\x5c\0\x46\x0a\x5d\0\x46\x0b\x5e\0\x47\x0d\x60\0\x47\x0e\x61\0\x47\x10\x63\0\
\x47\x11\x64\0\x47\x13\x65\0\x48\x14\x67\0\x48\x16\x68\0\x48\x17\x69\0\x48\x18\x6a\0\x48\x1a\x6c\0\x48\x1b\x6d\0\x48\x1c\x6e\0\x48\x1d\x6f\0\x48\x1f\x70\0\
\x48\x20\x71\0\x48\x21\x73\0\x48\x23\x74\0\x48\x24\x75\0\x48\x25\x76\0\x48\x26\x77\0\x48\x28\x78\0\x48\x29\x79\0\x47\x2a\x7a\0\x47\x2c\x7a\0\x47\x2d\x7b\0\
\x47\x2e\x7c\0\x47\x2f\x7d\0\x46\x30\x7e\0\x46\x32\x7e\0\x46\x33\x7f\0\x46\x34\x80\0\x45\x35\x81\0\x45\x37\x81\0\x45\x38\x82\0\x44\x39\x83\0\x44\x3a\x83\0\
\x44\x3b\x84\0\x43\x3d\x84\0\x43\x3e\x85\0\x42\x3f\x85\0\x42\x40\x86\0\x42\x41\x86\0\x41\x42\x87\0\x41\x44\x87\0\x40\x45\x88\0\x40\x46\x88\0\x3f\x47\x88\0\
\x3f\x48\x89\0\x3e\x49\x89\0\x3e\x4a\x89\0\x3e\x4c\x8a\0\x3d\x4d\x8a\0\x3d\x4e\x8a\0\x3c\x4f\x8a\0\x3c\x50\x8b\0\x3b\x51\x8b\0\x3b\x52\x8b\0\x3a\x53\x8b\0\
\x3a\x54\x8c\0\x39\x55\x8c\0\x39\x56\x8c\0\x38\x58\x8c\0\x38\x59\x8c\0\x37\x5a\x8c\0\x37\x5b\x8d\0\x36\x5c\x8d\0\x36\x5d\x8d\0\x35\x5e\x8d\0\x35\x5f\x8d\0\
\x34\x60\x8d\0\x34\x61\x8d\0\x33\x62\x8d\0\x33\x63\x8d\0\x32\x64\x8e\0\x32\x65\x8e\0\x31\x66\x8e\0\x31\x67\x8e\0\x31\x68\x8e\0\x30\x69\x8e\0\x30\x6a\x8e\0\
\x2f\x6b\x8e\0\x2f\x6c\x8e\0\x2e\x6d\x8e\0\x2e\x6e\x8e\0\x2e\x6f\x8e\0\x2d\x70\x8e\0\x2d\x71\x8e\0\x2c\x71\x8e\0\x2c\x72\x8e\0\x2c\x73\x8e\0\x2b\x74\x8e\0\
\x2b\x75\x8e\0\x2a\x76\x8e\0\x2a\x77\x8e\0\x2a\x78\x8e\0\x29\x79\x8e\0\x29\x7a\x8e\0\x29\x7b\x8e\0\x28\x7c\x8e\0\x28\x7d\x8e\0\x27\x7e\x8e\0\x27\x7f\x8e\0\
\x27\x80\x8e\0\x26\x81\x8e\0\x26\x82\x8e\0\x26\x82\x8e\0\x25\x83\x8e\0\x25\x84\x8e\0\x25\x85\x8e\0\x24\x86\x8e\0\x24\x87\x8e\0\x23\x88\x8e\0\x23\x89\x8e\0\
\x23\x8a\x8d\0\x22\x8b\x8d\0\x22\x8c\x8d\0\x22\x8d\x8d\0\x21\x8e\x8d\0\x21\x8f\x8d\0\x21\x90\x8d\0\x21\x91\x8c\0\x20\x92\x8c\0\x20\x92\x8c\0\x20\x93\x8c\0\
\x1f\x94\x8c\0\x1f\x95\x8b\0\x1f\x96\x8b\0\x1f\x97\x8b\0\x1f\x98\x8b\0\x1f\x99\x8a\0\x1f\x9a\x8a\0\x1e\x9b\x8a\0\x1e\x9c\x89\0\x1e\x9d\x89\0\x1f\x9e\x89\0\
\x1f\x9f\x88\0\x1f\xa0\x88\0\x1f\xa1\x88\0\x1f\xa1\x87\0\x1f\xa2\x87\0\x20\xa3\x86\0\x20\xa4\x86\0\x21\xa5\x85\0\x21\xa6\x85\0\x22\xa7\x85\0\x22\xa8\x84\0\
\x23\xa9\x83\0\x24\xaa\x83\0\x25\xab\x82\0\x25\xac\x82\0\x26\xad\x81\0\x27\xad\x81\0\x28\xae\x80\0\x29\xaf\x7f\0\x2a\xb0\x7f\0\x2c\xb1\x7e\0\x2d\xb2\x7d\0\
\x2e\xb3\x7c\0\x2f\xb4\x7c\0\x31\xb5\x7b\0\x32\xb6\x7a\0\x34\xb6\x79\0\x35\xb7\x79\0\x37\xb8\x78\0\x38\xb9\x77\0\x3a\xba\x76\0\x3b\xbb\x75\0\x3d\xbc\x74\0\
\x3f\xbc\x73\0\x40\xbd\x72\0\x42\xbe\x71\0\x44\xbf\x70\0\x46\xc0\x6f\0\x48\xc1\x6e\0\x4a\xc1\x6d\0\x4c\xc2\x6c\0\x4e\xc3\x6b\0\x50\xc4\x6a\0\x52\xc5\x69\0\
\x54\xc5\x68\0\x56\xc6\x67\0\x58\xc7\x65\0\x5a\xc8\x64\0\x5c\xc8\x63\0\x5e\xc9\x62\0\x60\xca\x60\0\x63\xcb\x5f\0\x65\xcb\x5e\0\x67\xcc\x5c\0\x69\xcd\x5b\0\
\x6c\xcd\x5a\0\x6e\xce\x58\0\x70\xcf\x57\0\x73\xd0\x56\0\x75\xd0\x54\0\x77\xd1\x53\0\x7a\xd1\x51\0\x7c\xd2\x50\0\x7f\xd3\x4e\0\x81\xd3\x4d\0\x84\xd4\x4b\0\
\x86\xd5\x49\0\x89\xd5\x48\0\x8b\xd6\x46\0\x8e\xd6\x45\0\x90\xd7\x43\0\x93\xd7\x41\0\x95\xd8\x40\0\x98\xd8\x3e\0\x9b\xd9\x3c\0\x9d\xd9\x3b\0\xa0\xda\x39\0\
\xa2\xda\x37\0\xa5\xdb\x36\0\xa8\xdb\x34\0\xaa\xdc\x32\0\xad\xdc\x30\0\xb0\xdd\x2f\0\xb2\xdd\x2d\0\xb5\xde\x2b\0\xb8\xde\x29\0\xba\xde\x28\0\xbd\xdf\x26\0\
\xc0\xdf\x25\0\xc2\xdf\x23\0\xc5\xe0\x21\0\xc8\xe0\x20\0\xca\xe1\x1f\0\xcd\xe1\x1d\0\xd0\xe1\x1c\0\xd2\xe2\x1b\0\xd5\xe2\x1a\0\xd8\xe2\x19\0\xda\xe3\x19\0\
\xdd\xe3\x18\0\xdf\xe3\x18\0\xe2\xe4\x18\0\xe5\xe4\x19\0\xe7\xe4\x19\0\xea\xe5\x1a\0\xec\xe5\x1b\0\xef\xe5\x1c\0\xf1\xe5\x1d\0\xf4\xe6\x1e\0\xf6\xe6\x20\0\
\xf8\xe6\x21\0\xfb\xe7\x23\0\xfd\xe7\x25\0'
SDL_PAL_VIRIDIS = (ctypes.c_uint8 * len(SDL_PAL_VIRIDIS_L))(*SDL_PAL_VIRIDIS_L)

# palettes from https://github.com/groupgets/GetThermal/blob/master/src/dataformatter.cpp
# print('\\\n'.join(re.findall('.{0,154}', ''.join([f'\\x{x[0:2]}\\x{x[2:4]}\\x{x[4:6]}\\0' for x in re.findall('......', bytes(a).hex())]))))
SDL_PAL_IRONBLACK_L = b'\
\xff\xff\xff\0\xfd\xfd\xfd\0\xfb\xfb\xfb\0\xf9\xf9\xf9\0\xf7\xf7\xf7\0\xf5\xf5\xf5\0\xf3\xf3\xf3\0\xf1\xf1\xf1\0\xef\xef\xef\0\xed\xed\xed\0\xeb\xeb\xeb\0\
\xe9\xe9\xe9\0\xe7\xe7\xe7\0\xe5\xe5\xe5\0\xe3\xe3\xe3\0\xe1\xe1\xe1\0\xdf\xdf\xdf\0\xdd\xdd\xdd\0\xdb\xdb\xdb\0\xd9\xd9\xd9\0\xd7\xd7\xd7\0\xd5\xd5\xd5\0\
\xd3\xd3\xd3\0\xd1\xd1\xd1\0\xcf\xcf\xcf\0\xcd\xcd\xcd\0\xcb\xcb\xcb\0\xc9\xc9\xc9\0\xc7\xc7\xc7\0\xc5\xc5\xc5\0\xc3\xc3\xc3\0\xc1\xc1\xc1\0\xbf\xbf\xbf\0\
\xbd\xbd\xbd\0\xbb\xbb\xbb\0\xb9\xb9\xb9\0\xb7\xb7\xb7\0\xb5\xb5\xb5\0\xb3\xb3\xb3\0\xb1\xb1\xb1\0\xaf\xaf\xaf\0\xad\xad\xad\0\xab\xab\xab\0\xa9\xa9\xa9\0\
\xa7\xa7\xa7\0\xa5\xa5\xa5\0\xa3\xa3\xa3\0\xa1\xa1\xa1\0\x9f\x9f\x9f\0\x9d\x9d\x9d\0\x9b\x9b\x9b\0\x99\x99\x99\0\x97\x97\x97\0\x95\x95\x95\0\x93\x93\x93\0\
\x91\x91\x91\0\x8f\x8f\x8f\0\x8d\x8d\x8d\0\x8b\x8b\x8b\0\x89\x89\x89\0\x87\x87\x87\0\x85\x85\x85\0\x83\x83\x83\0\x81\x81\x81\0\x7e\x7e\x7e\0\x7c\x7c\x7c\0\
\x7a\x7a\x7a\0\x78\x78\x78\0\x76\x76\x76\0\x74\x74\x74\0\x72\x72\x72\0\x70\x70\x70\0\x6e\x6e\x6e\0\x6c\x6c\x6c\0\x6a\x6a\x6a\0\x68\x68\x68\0\x66\x66\x66\0\
\x64\x64\x64\0\x62\x62\x62\0\x60\x60\x60\0\x5e\x5e\x5e\0\x5c\x5c\x5c\0\x5a\x5a\x5a\0\x58\x58\x58\0\x56\x56\x56\0\x54\x54\x54\0\x52\x52\x52\0\x50\x50\x50\0\
\x4e\x4e\x4e\0\x4c\x4c\x4c\0\x4a\x4a\x4a\0\x48\x48\x48\0\x46\x46\x46\0\x44\x44\x44\0\x42\x42\x42\0\x40\x40\x40\0\x3e\x3e\x3e\0\x3c\x3c\x3c\0\x3a\x3a\x3a\0\
\x38\x38\x38\0\x36\x36\x36\0\x34\x34\x34\0\x32\x32\x32\0\x30\x30\x30\0\x2e\x2e\x2e\0\x2c\x2c\x2c\0\x2a\x2a\x2a\0\x28\x28\x28\0\x26\x26\x26\0\x24\x24\x24\0\
\x22\x22\x22\0\x20\x20\x20\0\x1e\x1e\x1e\0\x1c\x1c\x1c\0\x1a\x1a\x1a\0\x18\x18\x18\0\x16\x16\x16\0\x14\x14\x14\0\x12\x12\x12\0\x10\x10\x10\0\x0e\x0e\x0e\0\
\x0c\x0c\x0c\0\x0a\x0a\x0a\0\x08\x08\x08\0\x06\x06\x06\0\x04\x04\x04\0\x02\x02\x02\0\x00\x00\x00\0\x00\x00\x09\0\x02\x00\x10\0\x04\x00\x18\0\x06\x00\x1f\0\
\x08\x00\x26\0\x0a\x00\x2d\0\x0c\x00\x35\0\x0e\x00\x3c\0\x11\x00\x43\0\x13\x00\x4a\0\x15\x00\x52\0\x17\x00\x59\0\x19\x00\x60\0\x1b\x00\x67\0\x1d\x00\x6f\0\
\x1f\x00\x76\0\x24\x00\x78\0\x29\x00\x79\0\x2e\x00\x7a\0\x33\x00\x7b\0\x38\x00\x7c\0\x3d\x00\x7d\0\x42\x00\x7e\0\x47\x00\x7f\0\x4c\x01\x80\0\x51\x01\x81\0\
\x56\x01\x82\0\x5b\x01\x83\0\x60\x01\x84\0\x65\x01\x85\0\x6a\x01\x86\0\x6f\x01\x87\0\x74\x01\x88\0\x79\x01\x88\0\x7d\x02\x89\0\x82\x02\x89\0\x87\x03\x89\0\
\x8b\x03\x8a\0\x90\x03\x8a\0\x95\x04\x8a\0\x99\x04\x8b\0\x9e\x05\x8b\0\xa3\x05\x8b\0\xa7\x05\x8c\0\xac\x06\x8c\0\xb1\x06\x8c\0\xb5\x07\x8d\0\xba\x07\x8d\0\
\xbd\x0a\x89\0\xbf\x0d\x84\0\xc2\x10\x7f\0\xc4\x13\x79\0\xc6\x16\x74\0\xc8\x19\x6f\0\xcb\x1c\x6a\0\xcd\x1f\x65\0\xcf\x22\x5f\0\xd1\x25\x5a\0\xd4\x28\x55\0\
\xd6\x2b\x50\0\xd8\x2e\x4b\0\xda\x31\x45\0\xdd\x34\x40\0\xdf\x37\x3b\0\xe0\x39\x31\0\xe1\x3c\x2f\0\xe2\x40\x2c\0\xe3\x43\x2a\0\xe4\x47\x27\0\xe5\x4a\x25\0\
\xe6\x4e\x22\0\xe7\x51\x20\0\xe7\x55\x1d\0\xe8\x58\x1b\0\xe9\x5c\x18\0\xea\x5f\x16\0\xeb\x63\x13\0\xec\x66\x11\0\xed\x6a\x0e\0\xee\x6d\x0c\0\xef\x70\x0c\0\
\xf0\x74\x0c\0\xf0\x77\x0c\0\xf1\x7b\x0c\0\xf1\x7f\x0c\0\xf2\x82\x0c\0\xf2\x86\x0c\0\xf3\x8a\x0c\0\xf3\x8d\x0d\0\xf4\x91\x0d\0\xf4\x95\x0d\0\xf5\x98\x0d\0\
\xf5\x9c\x0d\0\xf6\xa0\x0d\0\xf6\xa3\x0d\0\xf7\xa7\x0d\0\xf7\xab\x0d\0\xf8\xaf\x0e\0\xf8\xb2\x0f\0\xf9\xb6\x10\0\xf9\xb9\x12\0\xfa\xbd\x13\0\xfa\xc0\x14\0\
\xfb\xc4\x15\0\xfb\xc7\x16\0\xfc\xcb\x17\0\xfc\xce\x18\0\xfd\xd2\x19\0\xfd\xd5\x1b\0\xfe\xd9\x1c\0\xfe\xdc\x1d\0\xff\xe0\x1e\0\xff\xe3\x27\0\xff\xe5\x35\0\
\xff\xe7\x43\0\xff\xe9\x51\0\xff\xea\x5f\0\xff\xec\x6d\0\xff\xee\x7b\0\xff\xf0\x89\0\xff\xf2\x97\0\xff\xf4\xa5\0\xff\xf6\xb3\0\xff\xf8\xc1\0\xff\xf9\xcf\0\
\xff\xfb\xdd\0\xff\xfd\xeb\0\xff\xff\x18\0'
SDL_PAL_IRONBLACK = (ctypes.c_uint8 * len(SDL_PAL_IRONBLACK_L))(*SDL_PAL_IRONBLACK_L)

SDL_PAL_RAINBOW_L = b'\
\x01\x03\x4a\0\x00\x03\x4a\0\x00\x03\x4b\0\x00\x03\x4b\0\x00\x03\x4c\0\x00\x03\x4c\0\x00\x03\x4d\0\x00\x03\x4f\0\x00\x03\x52\0\x00\x05\x55\0\x00\x07\x58\0\
\x00\x0a\x5b\0\x00\x0e\x5e\0\x00\x13\x62\0\x00\x16\x64\0\x00\x19\x67\0\x00\x1c\x6a\0\x00\x20\x6d\0\x00\x23\x70\0\x00\x26\x74\0\x00\x28\x77\0\x00\x2a\x7b\0\
\x00\x2d\x80\0\x00\x31\x85\0\x00\x32\x86\0\x00\x33\x88\0\x00\x34\x89\0\x00\x35\x8b\0\x00\x36\x8e\0\x00\x37\x90\0\x00\x38\x91\0\x00\x3a\x95\0\x00\x3d\x9a\0\
\x00\x3f\x9c\0\x00\x41\x9f\0\x00\x42\xa1\0\x00\x44\xa4\0\x00\x45\xa7\0\x00\x47\xaa\0\x00\x49\xae\0\x00\x4b\xb3\0\x00\x4c\xb5\0\x00\x4e\xb8\0\x00\x4f\xbb\0\
\x00\x50\xbc\0\x00\x51\xbe\0\x00\x54\xc2\0\x00\x57\xc6\0\x00\x58\xc8\0\x00\x5a\xcb\0\x00\x5c\xcd\0\x00\x5e\xcf\0\x00\x5e\xd0\0\x00\x5f\xd1\0\x00\x60\xd2\0\
\x00\x61\xd3\0\x00\x63\xd6\0\x00\x66\xd9\0\x00\x67\xda\0\x00\x68\xdb\0\x00\x69\xdc\0\x00\x6b\xdd\0\x00\x6d\xdf\0\x00\x6f\xdf\0\x00\x71\xdf\0\x00\x73\xde\0\
\x00\x75\xdd\0\x00\x76\xdc\0\x01\x78\xdb\0\x01\x7a\xd9\0\x02\x7c\xd8\0\x02\x7e\xd6\0\x03\x81\xd4\0\x03\x83\xcf\0\x04\x84\xcd\0\x04\x85\xca\0\x04\x86\xc5\0\
\x05\x88\xc0\0\x06\x8a\xb9\0\x07\x8d\xb2\0\x08\x8e\xac\0\x0a\x90\xa6\0\x0a\x90\xa2\0\x0b\x91\x9e\0\x0c\x92\x99\0\x0d\x93\x95\0\x0f\x95\x8c\0\x11\x97\x84\0\
\x16\x99\x78\0\x19\x9a\x73\0\x1c\x9c\x6d\0\x22\x9e\x65\0\x28\xa0\x5e\0\x2d\xa2\x56\0\x33\xa4\x4f\0\x3b\xa7\x45\0\x43\xab\x3c\0\x48\xad\x36\0\x4e\xaf\x30\0\
\x53\xb1\x2b\0\x59\xb3\x27\0\x5d\xb5\x23\0\x62\xb7\x1f\0\x69\xb9\x1a\0\x6d\xbb\x17\0\x71\xbc\x15\0\x76\xbd\x13\0\x7b\xbf\x11\0\x80\xc1\x0e\0\x86\xc3\x0c\0\
\x8a\xc4\x0a\0\x8e\xc5\x08\0\x92\xc6\x06\0\x97\xc8\x05\0\x9b\xc9\x04\0\xa0\xcb\x03\0\xa4\xcc\x02\0\xa9\xcd\x02\0\xad\xce\x01\0\xaf\xcf\x01\0\xb2\xcf\x01\0\
\xb8\xd0\x00\0\xbe\xd2\x00\0\xc1\xd3\x00\0\xc4\xd4\x00\0\xc7\xd4\x00\0\xca\xd5\x01\0\xcf\xd6\x02\0\xd4\xd7\x03\0\xd7\xd6\x03\0\xda\xd6\x03\0\xdc\xd5\x03\0\
\xde\xd5\x04\0\xe0\xd4\x04\0\xe1\xd4\x05\0\xe2\xd4\x05\0\xe5\xd3\x05\0\xe8\xd3\x06\0\xe8\xd3\x06\0\xe9\xd3\x06\0\xea\xd2\x06\0\xeb\xd2\x07\0\xec\xd1\x07\0\
\xed\xd0\x08\0\xef\xce\x08\0\xf1\xcc\x09\0\xf2\xcb\x09\0\xf4\xca\x0a\0\xf4\xc9\x0a\0\xf5\xc8\x0a\0\xf5\xc7\x0b\0\xf6\xc6\x0b\0\xf7\xc5\x0c\0\xf8\xc2\x0d\0\
\xf9\xbf\x0e\0\xfa\xbd\x0e\0\xfb\xbb\x0f\0\xfb\xb9\x10\0\xfc\xb7\x11\0\xfc\xb2\x12\0\xfd\xae\x13\0\xfd\xab\x13\0\xfe\xa8\x14\0\xfe\xa5\x15\0\xfe\xa4\x15\0\
\xff\xa3\x16\0\xff\xa1\x16\0\xff\x9f\x17\0\xff\x9d\x17\0\xff\x9b\x18\0\xff\x95\x19\0\xff\x8f\x1b\0\xff\x8b\x1c\0\xff\x87\x1e\0\xff\x83\x1f\0\xff\x7f\x20\0\
\xff\x76\x22\0\xff\x6e\x24\0\xff\x68\x25\0\xff\x65\x26\0\xff\x63\x27\0\xff\x5d\x28\0\xff\x58\x2a\0\xfe\x52\x2b\0\xfe\x4d\x2d\0\xfe\x45\x2f\0\xfe\x3e\x31\0\
\xfd\x39\x32\0\xfd\x35\x34\0\xfc\x31\x35\0\xfc\x2d\x37\0\xfb\x27\x39\0\xfb\x21\x3b\0\xfb\x20\x3c\0\xfb\x1f\x3c\0\xfb\x1e\x3d\0\xfb\x1d\x3d\0\xfb\x1c\x3e\0\
\xfa\x1b\x3f\0\xfa\x1b\x41\0\xf9\x1a\x42\0\xf9\x1a\x44\0\xf8\x19\x46\0\xf8\x18\x49\0\xf7\x18\x4b\0\xf7\x19\x4d\0\xf7\x19\x4f\0\xf7\x1a\x51\0\xf7\x20\x53\0\
\xf7\x23\x55\0\xf7\x26\x56\0\xf7\x2a\x58\0\xf7\x2e\x5a\0\xf7\x32\x5c\0\xf8\x37\x5e\0\xf8\x3b\x60\0\xf8\x40\x62\0\xf8\x48\x65\0\xf9\x51\x68\0\xf9\x57\x6a\0\
\xfa\x5d\x6c\0\xfa\x5f\x6d\0\xfa\x62\x6e\0\xfa\x64\x6f\0\xfb\x65\x70\0\xfb\x66\x71\0\xfb\x6d\x75\0\xfc\x74\x79\0\xfc\x79\x7b\0\xfd\x7e\x7e\0\xfd\x82\x80\0\
\xfe\x87\x83\0\xfe\x8b\x85\0\xfe\x90\x88\0\xfe\x97\x8c\0\xff\x9e\x90\0\xff\xa3\x92\0\xff\xa8\x95\0\xff\xad\x98\0\xff\xb0\x99\0\xff\xb2\x9b\0\xff\xb8\xa0\0\
\xff\xbf\xa5\0\xff\xc3\xa8\0\xff\xc7\xac\0\xff\xcb\xaf\0\xff\xcf\xb3\0\xff\xd3\xb6\0\xff\xd8\xb9\0\xff\xda\xbe\0\xff\xdc\xc4\0\xff\xde\xc8\0\xff\xe1\xca\0\
\xff\xe3\xcc\0\xff\xe6\xce\0\xff\xe9\xd0\0'
SDL_PAL_RAINBOW = (ctypes.c_uint8 * len(SDL_PAL_RAINBOW_L))(*SDL_PAL_RAINBOW_L)

SDL_PALS = {
    'none': SDL_PAL_GRAYSCALE,
    'grayscale': SDL_PAL_GRAYSCALE,
    'inferno': SDL_PAL_INFERNO,
    'viridis': SDL_PAL_VIRIDIS,
    'ironblack': SDL_PAL_IRONBLACK,
    'rainbow': SDL_PAL_RAINBOW,
}

SDL_WINDOW_FULLSCREEN = 0x00000001
SDL_WINDOW_RESIZABLE = 0x00000020
SDL_WINDOW_FULLSCREEN_DESKTOP = (SDL_WINDOW_FULLSCREEN | 0x00001000)
SDL_WINDOW_ALLOW_HIGHDPI = 0x00002000
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

        try:
            self.fd = os.open(self.device, os.O_RDWR, 0)
        except Exception as e:
            logging.error(f'os.open: {e}')
            sys.exit(3)

        self.init_device()
        self.init_buffers()


    def init_device(self):
        cap = v4l2_capability()
        ioctl(self.fd, VIDIOC_QUERYCAP, cap)

        if not (cap.capabilities & V4L2_CAP_VIDEO_CAPTURE):
            logging.error(f'{self.device} is not a video capture device')
            sys.exit(3)

        if not (cap.capabilities & V4L2_CAP_STREAMING):
            logging.error(f'{self.device} does not support streaming i/o')
            sys.exit(3)
    
        fmt = v4l2_format()
        fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE
        ioctl(self.fd, VIDIOC_G_FMT, fmt)
    
        parm = v4l2_streamparm()
        parm.type = V4L2_BUF_TYPE_VIDEO_CAPTURE

        # Razer Kiyo Pro and Microsoft Lifecam HD-3000 need
        # to set FPS before first streaming
        ioctl(self.fd, VIDIOC_G_PARM, parm)

        try:
            ioctl(self.fd, VIDIOC_S_PARM, parm)
        except Exception as e:
            logging.error(f'VIDIOC_S_PARM failed {self.device}: {e}')
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
            logging.error(f'Video buffer request failed on {self.device}: {e}')
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
        try:
            ioctl(self.fd, VIDIOC_STREAMON, struct.pack('I', V4L2_BUF_TYPE_VIDEO_CAPTURE))
        except Exception as e:
            logging.error(f'VIDIOC_STREAMON failed {self.device}: {e}')
            self.pipe.write_buf(None)
            return

        for buf in self.cap_bufs:
            ioctl(self.fd, VIDIOC_QBUF, buf)

        qbuf = v4l2_buffer()
        qbuf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE
        qbuf.memory = self.cap_bufs[0].memory

        poll = select.poll()
        poll.register(self.fd, select.POLLIN)

        timeout = 0

        while not self.stopped:
            # DQBUF can block forever, so poll with 1000 ms timeout before
            # quit after 5s
            if len(poll.poll(1000)) == 0:
                logging.warning(f'{self.device}: timeout occured')
                timeout += 1
                if timeout == 5:
                    self.pipe.write_buf(None)
                    return
                continue

            try:
                ioctl(self.fd, VIDIOC_DQBUF, qbuf)
            except Exception as e:
                logging.error(f'VIDIOC_DQBUF failed {self.device}: {e}')
                self.pipe.write_buf(None)
                return

            buf = self.cap_bufs[qbuf.index]
            buf.bytesused = qbuf.bytesused
            buf.timestamp = qbuf.timestamp

            self.pipe.write_buf(buf)

            ioctl(self.fd, VIDIOC_QBUF, buf)

        try:
            ioctl(self.fd, VIDIOC_STREAMOFF, struct.pack('I', V4L2_BUF_TYPE_VIDEO_CAPTURE))
        except Exception as e:
            logging.error(f'VIDIOC_STREAMOFF failed {self.device}: {e}')

    def stop_capturing(self):
        self.stopped = True

    # thread start
    def run(self):
        self.capture_loop()
    
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
    # handling with surface+palette+texture, not here
    #elif format == V4L2_PIX_FMT_GREY:
    #    return SDL_PIXELFORMAT_INDEX8

    formats = 'Sorry, only YUYV, YVYU, UYVY, NV12, NV21, YU12, RGBP, RGB3, BGR3, RX24, MJPG, JPEG, GREY are supported yet.'
    logging.error(f'Invalid pixel format: {formats}')
    SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, b'Invalid pixel format', bytes(formats, 'utf-8'), None)
    sys.exit(3)

class SDLCameraWindow():
    def __init__(self, device, win_width, win_height, angle, flip, colormap):
        self.returncode = 0
        self.cam = V4L2Camera(device)
        self.cam.pipe = self
        self.ctrls = CameraCtrls(device, self.cam.fd)
        self.ptz = PTZController(self.ctrls)
        width = self.cam.width
        height = self.cam.height

        rwidth = self.cam.width
        rheight = self.cam.height
        if angle % 180 != 0:
            rwidth = self.cam.height
            rheight = self.cam.width

        win_width = rwidth if win_width == 0 else min(int(win_height * (rwidth/rheight)), win_width, rwidth)
        win_height = rheight if win_height == 0 else min(int(win_width * (rheight/rwidth)), win_height, rheight)

        self.fullscreen = False
        self.tj = None
        self.outbuffer = None
        self.bytesperline = self.cam.bytesperline
        self.surface = None
        self.surfbuffer = None

        self.angle = 0
        self.flip = 0
        self.dstrect = None
        self.colormap = None

        if self.cam.pixelformat in [V4L2_PIX_FMT_MJPEG, V4L2_PIX_FMT_JPEG]:
            self.tj = tj_init_decompress()
            # create rgb buffer
            self.outbuffer = (ctypes.c_uint8 * (width * height * 3))()
            self.bytesperline = width * 3

        if SDL_Init(SDL_INIT_VIDEO) != 0:
            logging.error(f'SDL_Init failed: {SDL_GetError()}')
            sys.exit(1)

        # create a new sdl user event type for new image events
        self.sdl_new_image_event = SDL_RegisterEvents(1)
        self.sdl_new_grey_image_event = SDL_RegisterEvents(1)
        self.sdl_camera_error_event = SDL_RegisterEvents(1)

        self.new_image_event = SDL_Event()
        self.new_image_event.type = self.sdl_new_image_event

        self.new_grey_image_event = SDL_Event()
        self.new_grey_image_event.type = self.sdl_new_grey_image_event

        self.camera_error_event = SDL_Event()
        self.camera_error_event.type = self.sdl_camera_error_event

        self.window = SDL_CreateWindow(bytes(device, 'utf-8'), SDL_WINDOWPOS_UNDEFINED, SDL_WINDOWPOS_UNDEFINED, win_width, win_height, SDL_WINDOW_RESIZABLE | SDL_WINDOW_ALLOW_HIGHDPI)
        if self.window is None:
            logging.error(f'SDL_CreateWindow failed: {SDL_GetError()}')
            sys.exit(1)
        self.renderer = SDL_CreateRenderer(self.window, -1, 0)
        if self.renderer is None:
            logging.error(f'SDL_CreateRenderer failed: {SDL_GetError()}')
            sys.exit(1)

        self.rotate(angle)
        self.mirror(flip)

        if self.cam.pixelformat != V4L2_PIX_FMT_GREY:
            self.texture = SDL_CreateTexture(self.renderer, V4L2Format2SDL(self.cam.pixelformat), SDL_TEXTUREACCESS_STREAMING, width, height)
            if self.texture is None:
                logging.error(f'SDL_CreateTexture failed: {SDL_GetError()}')
                sys.exit(1)

        self.surface = SDL_CreateRGBSurfaceFrom(self.surfbuffer, self.cam.width, self.cam.height, 8, self.cam.width, 0, 0, 0, 0)
        if not bool(self.surface):
            logging.error(f'SDL_CreateRGBSurfaceFrom failed: {SDL_GetError()}')
            sys.exit(1)

        self.colormaps = SDL_PALS
        if self.cam.pixelformat == V4L2_PIX_FMT_GREY:
            self.colormaps = {k: v for k, v in self.colormaps.items() if k != 'grayscale'}

        self.set_colormap(colormap)

    def write_buf(self, buf):
        if buf is None:
            SDL_PushEvent(ctypes.byref(self.camera_error_event))
            return

        ptr = (ctypes.c_uint8 * buf.bytesused).from_buffer(buf.buffer)
        event = self.new_image_event if self.cam.pixelformat != V4L2_PIX_FMT_GREY else self.new_grey_image_event

        if self.cam.pixelformat == V4L2_PIX_FMT_MJPEG or self.cam.pixelformat == V4L2_PIX_FMT_JPEG:
            tj_decompress(self.tj, ptr, buf.bytesused, self.outbuffer, self.cam.width, self.bytesperline, self.cam.height, TJPF_RGB, 0)
            # ignore decode errors, some cameras only send imperfect frames
            ptr = self.outbuffer

        if self.cam.pixelformat != V4L2_PIX_FMT_GREY and self.colormap != 'none':
            if self.surfbuffer is None:
                # create surface buffer as NV12, but use only the Y
                self.surfbuffer = (ctypes.c_uint8 * (self.cam.width * self.cam.height * 2))()
            SDL_ConvertPixels(self.cam.width, self.cam.height, V4L2Format2SDL(self.cam.pixelformat), ptr, self.bytesperline, SDL_PIXELFORMAT_NV12, self.surfbuffer, self.cam.width)
            ptr = self.surfbuffer
            event = self.new_grey_image_event

        event.user.data1 = ctypes.cast(ptr, ctypes.c_void_p)
        if SDL_PushEvent(ctypes.byref(event)) < 0:
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
                shift = event.key.keysym.mod & KMOD_SHIFT
                if event.key.keysym.sym == SDLK_f:
                    self.toggle_fullscreen()
                elif event.key.keysym.sym == SDLK_r:
                    self.rotate(90 if not shift else -90)
                elif event.key.keysym.sym == SDLK_m:
                    self.mirror(1 if not shift else -1)
                elif event.key.keysym.sym == SDLK_c:
                    self.step_colormap(1 if not shift else -1)
            elif event.type == SDL_MOUSEBUTTONUP and \
                event.button.button == SDL_BUTTON_LEFT and \
                event.button.clicks == 2:
                    self.toggle_fullscreen()
            elif event.type == self.sdl_new_image_event:
                if SDL_UpdateTexture(self.texture, None, event.user.data1, self.bytesperline) != 0:
                    logging.warning(f'SDL_UpdateTexture failed: {SDL_GetError()}')
                if SDL_RenderClear(self.renderer) != 0:
                    logging.warning(f'SDL_RenderClear failed: {SDL_GetError()}')
                if SDL_RenderCopyEx(self.renderer, self.texture, None, self.dstrect, self.angle, None, self.flip) != 0:
                    logging.warning(f'SDL_RenderCopy failed: {SDL_GetError()}')
                SDL_RenderPresent(self.renderer)
            elif event.type == self.sdl_new_grey_image_event:
                self.surface[0].pixels = event.user.data1
                texture = SDL_CreateTextureFromSurface(self.renderer, self.surface)
                if texture is None:
                    logging.warning(f'SDL_CreateTextureFromSurface failed: {SDL_GetError()}')
                    return
                if SDL_RenderClear(self.renderer) != 0:
                    logging.warning(f'SDL_RenderClear failed: {SDL_GetError()}')
                if SDL_RenderCopyEx(self.renderer, texture, None, self.dstrect, self.angle, None, self.flip) != 0:
                    logging.warning(f'SDL_RenderCopy failed: {SDL_GetError()}')
                SDL_RenderPresent(self.renderer)
                SDL_DestroyTexture(texture)
            elif event.type == self.sdl_camera_error_event:
                self.stop_capturing()
                self.returncode = 4
                break

            if event.type == SDL_KEYDOWN:
                if self.ptz.has_pantilt_speed:
                    if event.key.keysym.sym in [SDLK_LEFT, SDLK_KP_4, SDLK_KP_7, SDLK_KP_1, SDLK_a]:
                        self.ptz.do_pan_speed(-1, [])
                    if event.key.keysym.sym in [SDLK_RIGHT, SDLK_KP_6, SDLK_KP_9, SDLK_KP_3, SDLK_d]:
                        self.ptz.do_pan_speed(1, [])
                    if event.key.keysym.sym in [SDLK_UP, SDLK_KP_8, SDLK_KP_7, SDLK_KP_9, SDLK_w]:
                        self.ptz.do_tilt_speed(1, [])
                    if event.key.keysym.sym in [SDLK_DOWN, SDLK_KP_2, SDLK_KP_1, SDLK_KP_3, SDLK_s]:
                        self.ptz.do_tilt_speed(-1, [])
                    if event.key.keysym.sym == SDLK_KP_0:
                        self.ptz.do_reset([])
                elif self.ptz.has_pantilt_absolute:
                    if event.key.keysym.sym in [SDLK_LEFT, SDLK_KP_4, SDLK_KP_7, SDLK_KP_1, SDLK_a]:
                        self.ptz.do_pan_step(-1, [])
                    if event.key.keysym.sym in [SDLK_RIGHT, SDLK_KP_6, SDLK_KP_9, SDLK_KP_3, SDLK_d]:
                        self.ptz.do_pan_step(1, [])
                    if event.key.keysym.sym in [SDLK_UP, SDLK_KP_8, SDLK_KP_7, SDLK_KP_9, SDLK_w]:
                        self.ptz.do_tilt_step(1, [])
                    if event.key.keysym.sym in [SDLK_DOWN, SDLK_KP_2, SDLK_KP_1, SDLK_KP_3, SDLK_s]:
                        self.ptz.do_tilt_step(-1, [])
                    if event.key.keysym.sym == SDLK_KP_0:
                        self.ptz.do_reset([])
                if self.ptz.has_zoom_absolute:
                    ctrl = event.key.keysym.mod & KMOD_CTRL
                    if event.key.keysym.sym in [SDLK_KP_PLUS, SDLK_PLUS] and ctrl:
                        self.ptz.do_zoom_step_big(1, [])
                    elif event.key.keysym.sym in [SDLK_KP_MINUS, SDLK_MINUS] and ctrl:
                        self.ptz.do_zoom_step_big(-1, [])
                    elif event.key.keysym.sym in [SDLK_KP_PLUS, SDLK_PLUS]:
                        self.ptz.do_zoom_step(1, [])
                    elif event.key.keysym.sym in [SDLK_KP_MINUS, SDLK_MINUS]:
                        self.ptz.do_zoom_step(-1, [])
                    elif event.key.keysym.sym == SDLK_PAGEUP:
                        self.ptz.do_zoom_step_big(1, [])
                    elif event.key.keysym.sym == SDLK_PAGEDOWN:
                        self.ptz.do_zoom_step_big(-1, [])
                    elif event.key.keysym.sym == SDLK_HOME:
                        self.ptz.do_zoom_percent(0, [])
                    elif event.key.keysym.sym == SDLK_END:
                        self.ptz.do_zoom_percent(1, [])
                if event.key.keysym.sym == SDLK_1:
                    self.ptz.do_preset(1, [])
                elif event.key.keysym.sym == SDLK_2:
                    self.ptz.do_preset(2, [])
                elif event.key.keysym.sym == SDLK_3:
                    self.ptz.do_preset(3, [])
                elif event.key.keysym.sym == SDLK_4:
                    self.ptz.do_preset(4, [])
                elif event.key.keysym.sym == SDLK_5:
                    self.ptz.do_preset(5, [])
                elif event.key.keysym.sym == SDLK_6:
                    self.ptz.do_preset(6, [])
                elif event.key.keysym.sym == SDLK_7:
                    self.ptz.do_preset(7, [])
                elif event.key.keysym.sym == SDLK_8:
                    self.ptz.do_preset(8, [])
            elif event.type == SDL_KEYUP:
                if self.ptz.has_pantilt_speed:
                    if event.key.keysym.sym in [SDLK_LEFT, SDLK_KP_4, SDLK_KP_7, SDLK_KP_1, SDLK_a]:
                        self.ptz.do_pan_speed(0, [])
                    if event.key.keysym.sym in [SDLK_RIGHT, SDLK_KP_6, SDLK_KP_9, SDLK_KP_3, SDLK_d]:
                        self.ptz.do_pan_speed(0, [])
                    if event.key.keysym.sym in [SDLK_UP, SDLK_KP_8, SDLK_KP_7, SDLK_KP_9, SDLK_w]:
                        self.ptz.do_tilt_speed(0, [])
                    if event.key.keysym.sym in [SDLK_DOWN, SDLK_KP_2, SDLK_KP_1, SDLK_KP_3, SDLK_s]:
                        self.ptz.do_tilt_speed(0, [])

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        SDL_SetWindowFullscreen(self.window, SDL_WINDOW_FULLSCREEN_DESKTOP if self.fullscreen else 0)
        self.match_window_to_logical()

    def rotate(self, angle):
        self.angle += angle
        self.angle %= 360
        if self.angle % 180 == 0:
            self.dstrect = None
            if SDL_RenderSetLogicalSize(self.renderer, self.cam.width, self.cam.height) != 0:
                logging.warning(f'SDL_RenderSetlogicalSize failed: {SDL_GetError()}')
        else:
            self.dstrect = SDL_Rect(
                (self.cam.height - self.cam.width)//2,
                (self.cam.width - self.cam.height)//2,
                self.cam.width,
                self.cam.height
            )
            if SDL_RenderSetLogicalSize(self.renderer, self.cam.height, self.cam.width) != 0:
                logging.warning(f'SDL_RenderSetlogicalSize failed: {SDL_GetError()}')
        self.match_window_to_logical()
    
    def match_window_to_logical(self):
        if self.fullscreen:
            return

        win_w = ctypes.c_int()
        win_h = ctypes.c_int()
        SDL_GetWindowSize(self.window, win_w, win_h)

        logical_w = ctypes.c_int()
        logical_h = ctypes.c_int()
        SDL_RenderGetLogicalSize(self.renderer, logical_w, logical_h)

        if logical_w.value < logical_h.value and win_w.value < win_h.value:
            return
        if logical_w.value > logical_h.value and win_w.value > win_h.value:
            return
        
        SDL_SetWindowSize(self.window, win_h, win_w)

    def mirror(self, flip):
        self.flip += flip
        self.flip %= 4

    def set_colormap(self, colormap):
        if colormap not in self.colormaps:
            logging.warning(f'set_colormap: invalid colormap name ({colormap}) not in {list(SDL_PALS.keys())}')
            colormap = 'none'

        pal = self.colormaps.get(colormap)    

        self.colormap = colormap
        SDL_SetPaletteColors(self.surface[0].format[0].palette, pal, 0, 256)

    def step_colormap(self, step):
        cms = list(self.colormaps.keys())
        step = (cms.index(self.colormap) + step) % len(cms)
        self.set_colormap(cms[step])

    def start_capturing(self):
        self.cam.start()
        self.event_loop()

    def stop_capturing(self):
        self.cam.stop()

    def close(self):
        tj_destroy(self.tj)
        SDL_DestroyWindow(self.window)
        SDL_Quit()
        return self.returncode


def usage():
    print(f'usage: {sys.argv[0]} [--help] [-d DEVICE] [-s SIZE] [-r ANGLE] [-m FLIP] [-c COLORMAP]\n')
    print(f'optional arguments:')
    print(f'  -h, --help         show this help message and exit')
    print(f'  -d DEVICE          use DEVICE, default /dev/video0')
    print(f'  -s SIZE            put window inside SIZE rectangle (wxh), default unset')
    print(f'  -r ANGLE           rotate the image by ANGLE, default 0')
    print(f'  -m FLIP            mirror the image by FLIP, default no, (no, h, v, hv)')
    print(f'  -c COLORMAP        set colormap, default none')
    print(f'                    (none, grayscale, inferno, viridis, ironblack, rainbow)')
    print()
    print(f'example:')
    print(f'  {sys.argv[0]} -d /dev/video2')
    print()
    print(f'shortcuts:')
    print(f'  f: toggle fullscreen')
    print(f'  r: ANGLE +90 (shift+r -90)')
    print(f'  m: FLIP next (shift+m prev)')
    print(f'  c: COLORMAP next (shift+c prev)')


def main():
    try:
        arguments, values = getopt.getopt(sys.argv[1:], 'hd:s:r:m:c:', ['help'])
    except getopt.error as err:
        print(err)
        usage()
        sys.exit(2)

    device = '/dev/video0'
    width = 0
    height = 0
    angle = 0
    flip = 0
    colormap = 'none'

    for current_argument, current_value in arguments:
        if current_argument in ('-h', '--help'):
            usage()
            sys.exit(0)
        elif current_argument == '-d':
            device = current_value
        elif current_argument == '-s':
            args = current_value.split('x')
            if len(args) == 2:
                width = int(args[0])
                height = int(args[1])
            else:
                logging.warning(f'invalid size: {current_value}')
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
                logging.warning(f'invalid FLIP value: {current_value}')
        elif current_argument == '-c':
            colormap = current_value


    os.environ['SDL_VIDEO_X11_WMCLASS'] = 'hu.irl.cameractrls'
    os.environ['SDL_VIDEO_WAYLAND_WMCLASS'] = 'hu.irl.cameractrls'

    win = SDLCameraWindow(device, width, height, angle, flip, colormap)
    win.start_capturing()
    return win.close()


if __name__ == '__main__':
    sys.exit(main())
