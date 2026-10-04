# -*- coding: utf-8 -*-
"""最终回归：验证交付的 exe 完整可用。"""
import ctypes
import os
import shutil
import struct
import subprocess
import time

EXE = r'E:\Illusion\RapeLay\Illusion老游戏修复工具.exe'
PLANS = r'E:\Illusion\RapeLay\_方案切换'

print('=' * 62)
print('最终回归验证')
print('=' * 62)

print('\n[1] 交付物')
print('  exe: %.1f MB' % (os.path.getsize(EXE) / 1048576))

# 图标
n = ctypes.windll.user32.PrivateExtractIconsW(EXE, 0, 32, 32, None, None, 0, 0)
print('  exe 图标数(32x32) =', n)

print('\n[2] 方案目录完整（_方案切换）')
for d in ('方案A_DXVK', '方案B_dgVoodoo', '方案0_原生无补丁'):
    p = os.path.join(PLANS, d)
    if os.path.isdir(p):
        fs = os.listdir(p)
        print('  %-16s %d 文件: %s' % (d, len(fs), ', '.join(sorted(fs)[:7])))
    else:
        print('  %-16s !!! 缺失' % d)

# 关键 DLL 导出表检查
print('\n[3] 关键 DLL 导出表（Direct3DCreate9 必须在）')
def has_export(path, name):
    try:
        with open(path, 'rb') as f:
            data = f.read()
        return name.encode() in data
    except Exception:
        return False

for tag, p in (('A/d3d9.dll', os.path.join(PLANS, '方案A_DXVK', 'd3d9.dll')),
               ('B/d3d9.dll', os.path.join(PLANS, '方案B_dgVoodoo', 'd3d9.dll'))):
    print('  %-14s Direct3DCreate9=%s  大小=%d' % (
        tag, has_export(p, 'Direct3DCreate9'), os.path.getsize(p)))

print('\n[4] 兼容性标志（HKCU）')
import winreg
LAY = r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers'
with winreg.OpenKey(winreg.HKEY_CURRENT_USER, LAY, 0, winreg.KEY_READ) as k:
    nq = winreg.QueryInfoKey(k)[1]
    for i in range(nq):
        nm, v, _ = winreg.EnumValue(k, i)
        if isinstance(nm, str) and ('RapeLay' in nm and 'RapeLay_cn' in nm or
                                    'BotuPlay' in nm):
            print('  %s\n      = %s' % (nm, v))

print('\n[5] 游戏文件存在性')
for p in (r'E:\Illusion\RapeLay\RapeLay_cn.exe',
          r'E:\Illusion\RapeLay\[特典包BotuPlay]\BotuPlay.exe'):
    print('  %s  →  %s' % ('✔' if os.path.exists(p) else '✘', p))

print('\n[6] 当前部署状态（游戏目录内的代理 DLL）')
for d in (r'E:\Illusion\RapeLay',
          r'E:\Illusion\RapeLay\[特典包BotuPlay]'):
    prox = [f for f in os.listdir(d)
            if f.lower() in ('d3d9.dll', 'd3d8.dll', 'dxgi.dll', 'd3d11.dll',
                             'd3d10core.dll', 'ddraw.dll', 'd3dimm.dll',
                             'dxvk.conf', 'dgvoodoo.conf')]
    print('  %s' % d)
    print('     %s' % (', '.join(sorted(prox)) or '（无）'))

print('\n=' * 62)
print('REGRESSION DONE')
