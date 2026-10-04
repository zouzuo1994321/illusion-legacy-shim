# -*- coding: utf-8 -*-
"""
Magpie 对照实验
1) 记录 Magpie 当前 PID/路径（便于实验后重启）
2) 结束 Magpie
3) 启动 BotuPlay，逐秒采样窗口 / 卡死状态
4) 第 18 秒模拟点击
5) 结论对比
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


def windows_of_pid(pid):
    out = []

    def cb(hwnd, lparam):
        wpid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value != pid:
            return True
        ln = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(ln + 2)
        user32.GetWindowTextW(hwnd, buf, ln + 2)
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls, 256)
        rc = RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rc))
        style = user32.GetWindowLongW(hwnd, -16)
        out.append({
            'hwnd': hwnd, 'class': cls.value, 'title': buf.value,
            'rect': (rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top),
            'visible': bool(user32.IsWindowVisible(hwnd)),
            'hung': bool(user32.IsHungAppWindow(hwnd)),
            'style': hex(style & 0xFFFFFFFF),
        })
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return out


def proc_info(name):
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq ' + name, '/FO', 'CSV', '/NH'],
                       capture_output=True)
    o = r.stdout.decode('gbk', 'ignore').strip()
    if name.lower() not in o.lower():
        return None, None
    parts = [p.strip('"') for p in o.split('","')]
    try:
        return int(parts[1]), parts[4]
    except Exception:
        return None, None


print('=' * 62)
mp_pid, _ = proc_info('Magpie.exe')
print('[ENV] Magpie PID =', mp_pid)
if mp_pid:
    subprocess.run(['taskkill', '/F', '/PID', str(mp_pid)], capture_output=True)
    time.sleep(1.5)
    p2, _ = proc_info('Magpie.exe')
    print('[ENV] Magpie killed -> now:', p2)
print('=' * 62)

subprocess.run(['cmd', '/c', 'explorer.exe', EXE], capture_output=True)

pid = None
for _ in range(40):
    time.sleep(1)
    pid, mem = proc_info('BotuPlay.exe')
    if pid:
        break
print('[LAUNCH] BotuPlay PID =', pid)

for t in range(1, 33):
    time.sleep(1)
    alive, mem = proc_info('BotuPlay.exe')
    wins = windows_of_pid(pid) if alive and pid else []
    best = None
    for w in wins:
        if w['visible'] and w['rect'][2] > 100 and w['rect'][3] > 100:
            best = w
            break
    if best is None and wins:
        best = wins[0]
    info = ('%s cls=%s title=%r rect=%s vis=%s hung=%s style=%s' % (
        hex(best['hwnd']), best['class'], best['title'], best['rect'],
        best['visible'], best['hung'], best['style'])) if best else 'NO WINDOW'
    print('t=%02ds mem=%-10s wins=%d | %s' % (t, mem or 'DEAD', len(wins), info))

    if t == 18 and best and best['visible']:
        x = best['rect'][0] + best['rect'][2] // 2
        y = best['rect'][1] + best['rect'][3] // 2
        print('   >>> 点击 (%d,%d) hwnd=%s' % (x, y, hex(best['hwnd'])))
        user32.SetForegroundWindow(best['hwnd'])
        user32.SetCursorPos(x, y)
        time.sleep(0.3)
        user32.mouse_event(0x0002, 0, 0, 0, 0)
        time.sleep(0.05)
        user32.mouse_event(0x0004, 0, 0, 0, 0)
    if t == 25 and best:
        hung = user32.IsHungAppWindow(best['hwnd'])
        print('   >>> t=25s hung-check =', bool(hung))

print('=' * 62)
subprocess.run(['taskkill', '/F', '/IM', 'BotuPlay.exe'], capture_output=True)
