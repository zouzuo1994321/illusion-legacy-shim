# -*- coding: utf-8 -*-
"""更细致地观察 BotuPlay 窗口与卡死现象。"""
import subprocess, time, os, ctypes
from ctypes import wintypes

os.chdir(r'E:\Illusion\RapeLay\[特典包BotuPlay]')
user32 = ctypes.windll.user32

EnumWindows = user32.EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def all_windows():
    out = []

    def cb(hwnd, lparam):
        vis = user32.IsWindowVisible(hwnd)
        wpid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        ln = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(ln + 1)
        user32.GetWindowTextW(hwnd, buf, ln + 1)
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls, 256)
        if vis:
            out.append((hwnd, wpid.value, buf.value, cls.value))
        return True

    EnumWindows(EnumWindowsProc(cb), 0)
    return out


subprocess.run(['cmd', '/c', 'explorer.exe', os.path.join(os.getcwd(), 'BotuPlay.exe')],
               capture_output=True)
pid = None
for _ in range(40):
    time.sleep(1)
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq BotuPlay.exe', '/FO', 'CSV', '/NH'],
                       capture_output=True)
    o = r.stdout.decode('gbk', 'ignore').strip()
    if 'BotuPlay' in o:
        pid = int(o.split('","')[1].strip('"'))
        break
print('PID:', pid)
time.sleep(22)
print('=== 可见窗口 ===')
for h, p, t, c in all_windows():
    mark = ' <== BotuPlay' if p == pid else ''
    print('  hwnd=%s pid=%d class=%s title=%r%s' % (hex(h), p, c, t, mark))
subprocess.run(['taskkill', '/F', '/IM', 'BotuPlay.exe'], capture_output=True)
