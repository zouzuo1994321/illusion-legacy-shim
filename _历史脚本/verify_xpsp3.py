# -*- coding: utf-8 -*-
"""
验证 WINXPSP3 + RUNASADMIN 后 BotuPlay 是否正常：
- 用 ShellExecuteW runas 提权启动（与用户双击等效）
- 逐秒采样：进程内存、窗口(enabled 含隐藏)、IsHungAppWindow
- 关键判据：能否枚举到游戏主窗口（此前一直 wins=0）
- 第 20 秒模拟点击，第 25 秒检查是否 hung
"""
import ctypes
import os
import subprocess
import time
from ctypes import wintypes

GAME_DIR = r'E:\Illusion\RapeLay\[特典包BotuPlay]'
EXE = os.path.join(GAME_DIR, 'BotuPlay.exe')

shell32 = ctypes.windll.shell32
user32 = ctypes.windll.user32
user32.IsHungAppWindow.restype = wintypes.BOOL
user32.IsHungAppWindow.argtypes = [wintypes.HWND]


class RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def wins_of(pid):
    out = []

    def cb(hwnd, lparam):
        wpid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value != pid:
            return True
        rc = RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rc))
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls, 256)
        ln = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(ln + 2)
        user32.GetWindowTextW(hwnd, buf, ln + 2)
        out.append({
            'hwnd': hwnd, 'class': cls.value, 'title': buf.value,
            'rect': (rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top),
            'visible': bool(user32.IsWindowVisible(hwnd)),
            'hung': bool(user32.IsHungAppWindow(hwnd)),
            'enabled': bool(user32.IsWindowEnabled(hwnd)),
        })
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return out


def procs():
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq BotuPlay.exe', '/FO', 'CSV', '/NH'],
                       capture_output=True)
    o = r.stdout.decode('gbk', 'ignore').strip()
    out = []
    if 'BotuPlay' not in o:
        return out
    for line in o.splitlines():
        p = [x.strip('"') for x in line.strip().split('","')]
        if len(p) >= 5 and not line.startswith('信息'):
            out.append((p[1], p[4]))
    return out


# 提权启动（等同用户右键“以管理员身份运行”）
r = shell32.ShellExecuteW(None, 'runas', EXE, None, GAME_DIR, 1)
print('[LAUNCH] ShellExecuteW runas ->', r, '(>32 表示成功)')

pid = None
for _ in range(40):
    time.sleep(1)
    ps = procs()
    if ps:
        pid = int(ps[0][0])
        break
print('[PID] =', pid)

if not pid:
    print('!! 启动失败')
    raise SystemExit(1)

for t in range(1, 36):
    time.sleep(1)
    ps = procs()
    alive = any(int(p[0]) == pid for p in ps)
    mem = next((p[1] for p in ps if int(p[0]) == pid), 'DEAD')
    ws = wins_of(pid) if alive else []
    vis = [w for w in ws if w['visible'] and w['rect'][2] > 50 and w['rect'][3] > 50]
    pick = vis[0] if vis else (ws[0] if ws else None)
    info = ('%s cls=%s title=%r rect=%s vis=%s hung=%s en=%s' % (
        hex(pick['hwnd']), pick['class'], pick['title'], pick['rect'],
        pick['visible'], pick['hung'], pick['enabled'])) if pick else 'NO WINDOW'
    print('t=%02ds mem=%-11s wins=%d vis=%d | %s' % (t, mem, len(ws), len(vis), info))

    if t == 20 and pick and pick['visible']:
        x = pick['rect'][0] + pick['rect'][2] // 2
        y = pick['rect'][1] + pick['rect'][3] // 2
        print('   >>> 模拟点击 (%d,%d) hwnd=%s' % (x, y, hex(pick['hwnd'])))
        user32.SetForegroundWindow(pick['hwnd'])
        user32.SetCursorPos(x, y)
        time.sleep(0.3)
        user32.mouse_event(0x0002, 0, 0, 0, 0)
        time.sleep(0.05)
        user32.mouse_event(0x0004, 0, 0, 0, 0)
    if t == 26 and pick:
        h = user32.IsHungAppWindow(pick['hwnd'])
        print('   >>> t=26s hung =', bool(h), '  (False = 未卡死 ✓)')

print('\n最终进程:', procs())
subprocess.run(['taskkill', '/F', '/IM', 'BotuPlay.exe'], capture_output=True)
