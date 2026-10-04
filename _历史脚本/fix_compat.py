# -*- coding: utf-8 -*-
"""
为 Illusion 老游戏写入兼容性标志：
  目标值 = "~ WINXPSP3 RUNASADMIN"

写入位置（三层，覆盖面最全）：
  1) HKCU\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\AppCompatFlags\\Layers
     （当前用户层，最常用）
  2) HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\AppCompatFlags\\Layers
     （机器层，需要管理员权限；失败则跳过）
  3) HKLM\\...\\WOW6432Node\\... （32 位视图，部分系统在此生效）

同时清理旧的错误值（WINXPSP2 版本）。
"""
import winreg
import os
import sys

LAYERS = r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers'
TARGET = '~ WINXPSP3 RUNASADMIN'

# 需要修复的可执行文件（两份拷贝都覆盖）
TARGETS = [
    r'E:\Illusion\RapeLay\RapeLay_cn.exe',
    r'E:\Illusion\RapeLay\[特典包BotuPlay]\BotuPlay.exe',
    r'E:\Illusion\电车之狼R+特典包+去码+中文+真人私出+看图档(带全补丁)\RapeLay_cn.exe',
    r'E:\Illusion\电车之狼R+特典包+去码+中文+真人私出+看图档(带全补丁)\[特典包BotuPlay]\BotuPlay.exe',
]

VIEWS = [
    ('HKCU', winreg.HKEY_CURRENT_USER, 0, winreg.KEY_SET_VALUE | winreg.KEY_READ),
    ('HKLM', winreg.HKEY_LOCAL_MACHINE, 0, winreg.KEY_SET_VALUE | winreg.KEY_READ | winreg.KEY_WOW64_64KEY),
    ('HKLM32', winreg.HKEY_LOCAL_MACHINE, 0, winreg.KEY_SET_VALUE | winreg.KEY_READ | winreg.KEY_WOW64_32KEY),
]


def read_val(hive, access):
    try:
        k = winreg.OpenKey(hive, LAYERS, 0, access)
        try:
            out = {}
            n = winreg.QueryInfoKey(k)[1]
            for i in range(n):
                name, val, _ = winreg.EnumValue(k, i)
                out[name] = val
            return out
        finally:
            winreg.CloseKey(k)
    except FileNotFoundError:
        return {}
    except OSError as e:
        return {'__err__': str(e)}


print('=' * 70)
print('修改前：')
for label, hive, _r, access in VIEWS:
    r = read_val(hive, access)
    print(' [%s] 共 %d 项' % (label, len(r)))
    for name, val in r.items():
        if isinstance(name, str) and ('rape' in name.lower() or 'botu' in name.lower()):
            print('     %s = %s' % (name, val))

print()
print('=' * 70)
print('写入目标值: %r' % TARGET)
print('=' * 70)

results = []
for exe in TARGETS:
    if not os.path.exists(exe):
        print('!! 跳过（文件不存在）: %s' % exe)
        results.append((exe, 'SKIP'))
        continue
    ok_any = False
    for label, hive, _r, access in VIEWS:
        try:
            if label == 'HKCU':
                k = winreg.CreateKeyEx(hive, LAYERS, 0, winreg.KEY_SET_VALUE)
            else:
                k = winreg.CreateKeyEx(hive, LAYERS, 0,
                                       winreg.KEY_SET_VALUE | access & winreg.KEY_WOW64_32KEY)
            winreg.SetValueEx(k, exe, 0, winreg.REG_SZ, TARGET)
            winreg.CloseKey(k)
            ok_any = True
            print('  [OK  %s] %s' % (label, exe))
        except PermissionError:
            print('  [拒绝 %s] 需管理员（已跳过）: %s' % (label, exe))
        except Exception as e:
            print('  [失败 %s] %s -> %s' % (label, exe, e))
    results.append((exe, 'OK' if ok_any else 'FAIL'))

print()
print('=' * 70)
print('修改后：')
for label, hive, _r, access in VIEWS:
    r = read_val(hive, access)
    print(' [%s]' % label)
    for name, val in r.items():
        if isinstance(name, str) and ('rape' in name.lower() or 'botu' in name.lower()):
            print('     %s = %s' % (name, val))

print()
print('=' * 70)
print('结果汇总：')
for exe, st in results:
    print('  %-6s %s' % (st, exe))
