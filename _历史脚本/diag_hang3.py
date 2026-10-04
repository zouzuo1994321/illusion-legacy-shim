# -*- coding: utf-8 -*-
"""
BotuPlay 卡死诊断 v3
策略：
1) 记录启动前 Magpie 是否在运行（用户环境有 Magpie 窗口缩放器，高度可疑）
2) 启动 BotuPlay.exe，逐 2 秒采样：
   - 进程是否存活 / 内存
   - 该进程所有顶层窗口：hwnd / class / title / rect / visible / IsHungAppWindow
   - 主窗口 rect 是否为 0x0（DXVK swapchain 请求 0x0 的直接证据）
3) 第 20 秒模拟一次点击（游戏窗口中心），观察卡死窗口归属
4) 输出结论
"""
import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes

GAME_DIR = r'E:\Illusion\RapeLay\[特典包BotuPlay]'
EXE = os.path.join(GAME_DIR, 'BotuPlay.exe')

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
user32.IsHungAppWindow.restype = wintypes.BOOL
user32.IsHungAppWindow.argtypes = [wintypes.HWND]


class RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


EnumWindows = user32.EnumWindows
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
        out.append({
            'hwnd': hwnd,
            'class': cls.value,
            'title': buf.value,
            'rect': (rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top),
            'visible': bool(user32.IsWindowVisible(hwnd)),
            'hung': bool(user32.IsHungAppWindow(hwnd)),
        })
        return True

    EnumWindows(EnumWindowsProc(cb), 0)
    return out


def pid_of(name):
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq ' + name, '/FO', 'CSV', '/NH'],
                       capture_output=True)
    o = r.stdout.decode('gbk', 'ignore').strip()
    if name.lower() not in o.lower() or 'no tasks' in o.lower():
        return None, None
    parts = [p.strip('"') for p in o.split('","')]
    try:
        return int(parts[1]), parts[4]
    except Exception:
        return None, None


def magpie_running():
    p, _ = pid_of('Magpie.exe')
    return p


print('=' * 60)
mp = magpie_running()
print('[ENV] Magpie.exe PID =', mp)
print('=' * 60)

subprocess.run(['cmd', '/c', 'explorer.exe', EXE], capture_output=True)

pid = None
for _ in range(40):
    time.sleep(1)
    pid, mem = pid_of('BotuPlay.exe')
    if pid:
        break
print('[LAUNCH] BotuPlay PID =', pid, 'mem =', mem)

if not pid:
    print('!! 进程未启动')
    sys.exit(1)

timeline = []
for t in range(1, 31):
    time.sleep(1)
    alive, mem = pid_of('BotuPlay.exe')
    wins = windows_of_pid(pid) if alive else []
    target = None
    for w in wins:
        if w['visible'] and w['rect'][2] > 100 and w['rect'][3] > 100:
            target = w
            break
    if target is None and wins:
        target = wins[0]
    if target:
        info = '%s cls=%s title=%r rect=%s vis=%s hung=%s' % (
            hex(target['hwnd']), target['class'], target['title'],
            target['rect'], target['visible'], target['hung'])
    else:
        info = 'NO WINDOW'
    print('t=%02ds alive=%s mem=%s wins=%d | %s' % (t, bool(alive), mem, len(wins), info))
    timeline.append((t, bool(alive), info, target))

    # 第 20 秒模拟点击
    if t == 20 and target and target['visible']:
        x = target['rect'][0] + target['rect'][2] // 2
        y = target['rect'][1] + target['rect'][3] // 2
        print('   >>> 模拟点击 (%d,%d)' % (x, y))
        user32.SetForegroundWindow(target['hwnd'])
        user32.SetCursorPos(x, y)
        time.sleep(0.3)
        user32.mouse_event(0x0002, 0, 0, 0, 0)  # LEFTDOWN
        time.sleep(0.05)
        user32.mouse_event(0x0004, 0, 0, 0, 0)  # LEFTUP

print('=' * 60)
print('[RESULT] 最终窗口状态：')
for w in windows_of_pid(pid):
    print('   ', w)
subprocess.run(['taskkill', '/F', '/IM', 'BotuPlay.exe'], capture_output=True)
