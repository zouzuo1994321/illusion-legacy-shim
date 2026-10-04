# -*- coding: utf-8 -*-
"""真机截图：启动新 exe，抓窗口截图（验证 UI 高度 + logo）。"""
import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes

EXE = r'E:\Illusion\RapeLay\Illusion老游戏修复工具.exe'
OUT = r'E:\Illusion\RapeLay\_switcher_src\ui_shot_new.png'

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

class RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]

# 启动
subprocess.Popen([EXE])
print('已启动，等待 8 秒渲染 ...')
time.sleep(8)

# 找窗口
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
found = []

def cb(hwnd, lparam):
    if not user32.IsWindowVisible(hwnd):
        return True
    ln = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(ln + 2)
    user32.GetWindowTextW(hwnd, buf, ln + 2)
    if 'Illusion' in buf.value or '修复' in buf.value:
        found.append((hwnd, buf.value))
    return True

user32.EnumWindows(EnumWindowsProc(cb), 0)
print('找到窗口:', [(hex(h), t) for h, t in found])

if not found:
    print('未找到窗口')
    subprocess.run(['taskkill', '/F', '/IM', 'Illusion老游戏修复工具.exe'],
                   capture_output=True)
    sys.exit(1)

hwnd, title = found[0]
rc = RECT()
user32.GetWindowRect(hwnd, ctypes.byref(rc))
w = rc.right - rc.left
h = rc.bottom - rc.top
print('窗口尺寸 = %dx%d' % (w, h))

# 截图（含窗口）
user32.SetForegroundWindow(hwnd)
time.sleep(1)

hwndDC = user32.GetWindowDC(hwnd)
mfcDC = gdi32.CreateCompatibleDC(hwndDC)
bmp = gdi32.CreateCompatibleBitmap(hwndDC, w, h)
gdi32.SelectObject(mfcDC, bmp)

# PrintWindow 抓取
r = user32.PrintWindow(hwnd, mfcDC, 2)
print('PrintWindow 返回 =', r)

# 用 PIL 取位图
from PIL import Image
class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [('biSize', ctypes.c_uint32), ('biWidth', ctypes.c_long),
                ('biHeight', ctypes.c_long), ('biPlanes', ctypes.c_ushort),
                ('biBitCount', ctypes.c_ushort), ('biCompression', ctypes.c_uint32),
                ('biSizeImage', ctypes.c_uint32), ('biXPelsPerMeter', ctypes.c_long),
                ('biYPelsPerMeter', ctypes.c_long), ('biClrUsed', ctypes.c_uint32),
                ('biClrImportant', ctypes.c_uint32)]

bi = BITMAPINFOHEADER()
bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
bi.biWidth = w
bi.biHeight = -h  # top-down
bi.biPlanes = 1
bi.biBitCount = 32
bi.biCompression = 0

buf = ctypes.create_string_buffer(w * h * 4)
lines = gdi32.GetDIBits(mfcDC, bmp, 0, h, buf, ctypes.byref(bi), 0)
print('GetDIBits 行数 =', lines)

img = Image.frombuffer('RGBA', (w, h), buf, 'raw', 'BGRA', 0, 1)
img = img.convert('RGB')
img.save(OUT)
print('已保存:', OUT, img.size)

gdi32.DeleteObject(bmp)
gdi32.DeleteDC(mfcDC)
user32.ReleaseDC(hwnd, hwndDC)
subprocess.run(['taskkill', '/F', '/IM', 'Illusion老游戏修复工具.exe'], capture_output=True)
