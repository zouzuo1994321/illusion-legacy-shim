# -*- coding: utf-8 -*-
"""复现 BotuPlay 卡死：启动 -> 等画面 -> 模拟鼠标点击 -> 监控响应。"""
import subprocess, time, os, ctypes
from ctypes import wintypes

os.chdir(r'E:\Illusion\RapeLay\[特典包BotuPlay]')

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# 进程/窗口相关
EnumWindows = user32.EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def find_window(pid):
    result = []

    def cb(hwnd, lparam):
        wpid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value == pid and user32.IsWindowVisible(hwnd):
            ln = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(ln + 1)
            user32.GetWindowTextW(hwnd, buf, ln + 1)
            result.append((hwnd, buf.value))
        return True

    EnumWindows(EnumWindowsProc(cb), 0)
    return result


def is_hung(hwnd):
    """SendMessageTimeout 检查窗口是否响应。"""
    SMTO_ABORTIFHUNG = 0x0002
    res = ctypes.c_ulonglong(0)
    r = user32.SendMessageTimeoutW(hwnd, 0x0000, 0, 0, SMTO_ABORTIFHUNG, 1500,
                                   ctypes.byref(res))
    return r == 0


print('启动 BotuPlay.exe ...')
subprocess.run(['cmd', '/c', 'explorer.exe', os.path.join(os.getcwd(), 'BotuPlay.exe')],
               capture_output=True)

# 找 PID
pid = None
for _ in range(40):
    time.sleep(1)
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq BotuPlay.exe', '/FO', 'CSV', '/NH'],
                       capture_output=True)
    out = r.stdout.decode('gbk', 'ignore').strip()
    if 'BotuPlay' in out:
        pid = int(out.split('","')[1].strip('"'))
        break

if not pid:
    print('未找到进程'); raise SystemExit

print('PID =', pid)
time.sleep(20)  # 等画面

wins = find_window(pid)
print('窗口:', [(hex(h), t) for h, t in wins])
if not wins:
    print('没找到可见窗口'); raise SystemExit

hwnd = wins[0][0]
print('卡死检测(点击前):', is_hung(hwnd))

# 模拟点击窗口中心
rect = wintypes.RECT()
user32.GetClientRect(hwnd, ctypes.byref(rect))
cx = (rect.right - rect.left) // 2
cy = (rect.bottom - rect.top) // 2
print('发送点击 (%d,%d) ...' % (cx, cy))
lp = (cy << 16) | (cx & 0xFFFF)
user32.PostMessageW(hwnd, 0x0201, 1, lp)   # WM_LBUTTONDOWN
time.sleep(0.05)
user32.PostMessageW(hwnd, 0x0202, 0, lp)   # WM_LBUTTONUP

# 监控 15 秒
for i in range(15):
    time.sleep(1)
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq BotuPlay.exe', '/FO', 'CSV', '/NH'],
                       capture_output=True)
    alive = 'BotuPlay' in r.stdout.decode('gbk', 'ignore')
    hung = is_hung(hwnd) if alive else None
    print('  %2ds: alive=%s hung=%s' % (i + 1, alive, hung))
    if not alive:
        break

subprocess.run(['taskkill', '/F', '/IM', 'BotuPlay.exe'], capture_output=True)
print('done')
