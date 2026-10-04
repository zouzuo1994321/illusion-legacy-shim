# -*- coding: utf-8 -*-
"""
深度窗口枚举：找出 BotuPlay 到底有没有窗口（含隐藏/子窗口/工具窗口），
并检查窗口 style 里是否含 WS_VISIBLE(0x10000000)、WS_DISABLED(0x08000000)、
WS_EX_ 相关；同时读窗口 text、类名，判断是否被 DXVK 接管。
另外：检查该进程所有线程的挂起/等待状态（用 NtQuerySystemInformation 太复杂，
改为用 GetGUIThreadInfo + IsHungAppWindow 覆盖所有线程窗口）。
"""
import ctypes
import os
import subprocess
import time
from ctypes import wintypes

GAME_DIR = r'E:\Illusion\RapeLay\[特典包BotuPlay]'
EXE = os.path.join(GAME_DIR, 'BotuPlay.exe')

user32 = ctypes.windll.user32
user32.IsHungAppWindow.restype = wintypes.BOOL
user32.IsHungAppWindow.argtypes = [wintypes.HWND]


class RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def all_windows_of_pid(pid):
    out = []

    def cb(hwnd, lparam):
        wpid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value != pid:
            return True
        rc = RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rc))
        cls = ctypes.create_unicode_buffer(512)
        user32.GetClassNameW(hwnd, cls, 512)
        ln = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(ln + 2)
        user32.GetWindowTextW(hwnd, buf, ln + 2)
        st = user32.GetWindowLongW(hwnd, -16) & 0xFFFFFFFF
        ex = user32.GetWindowLongW(hwnd, -20) & 0xFFFFFFFF
        out.append({
            'hwnd': hwnd, 'class': cls.value, 'title': buf.value,
            'rect': (rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top),
            'visible': bool(user32.IsWindowVisible(hwnd)),
            'hung': bool(user32.IsHungAppWindow(hwnd)),
            'style': st, 'exstyle': ex,
            'parent': user32.GetParent(hwnd),
            'owner': user32.GetWindow(hwnd, 4),  # GW_OWNER
        })
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return out


def proc(name):
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq ' + name, '/FO', 'CSV', '/NH'],
                       capture_output=True)
    o = r.stdout.decode('gbk', 'ignore').strip()
    if name.lower() not in o.lower():
        return None, None
    p = [x.strip('"') for x in o.split('","')]
    try:
        return int(p[1]), p[4]
    except Exception:
        return None, None


subprocess.run(['cmd', '/c', 'explorer.exe', EXE], capture_output=True)
pid = None
for _ in range(40):
    time.sleep(1)
    pid, mem = proc('BotuPlay.exe')
    if pid:
        break
print('PID =', pid)

for t in range(1, 40):
    time.sleep(1)
    if t == 22:
        break

print('\n===== 全部窗口（含隐藏）枚举 @ t=22s =====')
wins = all_windows_of_pid(pid)
print('窗口总数 =', len(wins))
for w in wins:
    print('  hwnd=%s parent=%s owner=%s' % (hex(w['hwnd']), hex(w['parent'] or 0), hex(w['owner'] or 0)))
    print('    class=%r title=%r' % (w['class'], w['title']))
    print('    rect=%s visible=%s hung=%s' % (w['rect'], w['visible'], w['hung']))
    print('    style=0x%08X WS_VISIBLE=%s WS_DISABLED=%s WS_POPUP=%s WS_CHILD=%s' % (
        w['style'],
        bool(w['style'] & 0x10000000),
        bool(w['style'] & 0x08000000),
        bool(w['style'] & 0x80000000),
        bool(w['style'] & 0x40000000)))
    print('    exstyle=0x%08X WS_EX_TOOLWINDOW=%s WS_EX_APPWINDOW=%s WS_EX_NOREDIRECTION=%s' % (
        w['exstyle'],
        bool(w['exstyle'] & 0x00000080),
        bool(w['exstyle'] & 0x00040000),
        bool(w['exstyle'] & 0x00200000)))

print('\n===== DXVK 是否创建了 Vulkan 呈现窗口（查 vulkan-1.dll 模块）=====')
subprocess.run(['tasklist', '/M', '/FI', 'IMAGENAME eq BotuPlay.exe', '/FO', 'CSV', '/NH'],
               capture_output=True)
r = subprocess.run(['tasklist', '/M', '/FI', 'IMAGENAME eq BotuPlay.exe'],
                   capture_output=True)
print(r.stdout.decode('gbk', 'ignore')[:3000])

subprocess.run(['taskkill', '/F', '/IM', 'BotuPlay.exe'], capture_output=True)
