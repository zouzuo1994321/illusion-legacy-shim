# -*- coding: utf-8 -*-
"""
OS2 专用方案目录 E2E（在临时目录模拟大写环境，不碰真实 OS2）。
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main as M

SRC = r'E:\Illusion\RapeLay\_方案切换'
LOGS = []
def log(m, *a):
    if a:
        try:
            m = m % a
        except Exception:
            pass
    LOGS.append(m)

# 模拟一个"大写 dgVoodoo 环境"的游戏目录
td = tempfile.mkdtemp(prefix='os2_sim_')
game = os.path.join(td, 'OS2')
os.makedirs(game)
# 模仿 OS2 现状：大写 dgVoodoo
bk = r'E:\Illusion\OS2\_switcher_backup\20261004_初始dgVoodoo状态'
mapping = {'D3D9.dll': 'D3D9.dll', 'D3D8.dll': 'D3D8.dll',
           'DDraw.dll': 'DDraw.dll', 'D3DImm.dll': 'D3DImm.dll',
           'dgVoodoo.conf': 'dgVoodoo.conf', 'dgVoodooCpl.exe': 'dgVoodooCpl.exe'}
for s, d in mapping.items():
    shutil.copy2(os.path.join(bk, s), os.path.join(game, d))
open(os.path.join(game, 'OS2cn.exe'), 'wb').write(b'MZ')

def listing():
    return sorted(f for f in os.listdir(game)
                  if f.lower() in [x.lower() for x in M.PLAN_FILES]
                  or f.endswith('.off'))

def no_dup():
    low = [f.lower() for f in os.listdir(game)]
    return len(low) == len(set(low))

print('初始（大写 dgVoodoo）:', listing())
assert no_dup()

print('\n--- 方案A (DXVK) ---')
M.deploy(game, 'A', SRC, log)
print('  ', listing(), '| 方案 =', M.detect_plan(game), '| 无重名 =', no_dup())
assert M.detect_plan(game) == 'A'
assert no_dup()

print('\n--- 方案B (优先 OS2 专用目录) ---')
M.deploy(game, 'B', SRC, log, overrides={'B': '方案B_dgVoodoo_OS2'})
print('  ', listing(), '| 方案 =', M.detect_plan(game), '| 无重名 =', no_dup())
assert M.detect_plan(game) == 'B'
assert no_dup()
# 校验用的是 OS2 版 dgVoodoo（474624 字节）
d9 = os.path.join(game, 'd3d9.dll')
print('   d3d9.dll 大小 =', os.path.getsize(d9), '(应 474624 = OS2 旧版)')
assert os.path.getsize(d9) == 474624

print('\n--- 方案B (不带 overrides，应使用标准 dgVoodoo 482304) ---')
M.deploy(game, 'B', SRC, log)
print('   d3d9.dll 大小 =', os.path.getsize(d9), '(应 482304 = 标准版)')
assert os.path.getsize(d9) == 482304

print('\n--- 方案0 (还原) ---')
M.deploy(game, '0', SRC, log)
print('  ', listing(), '| 无重名 =', no_dup())
for n in M.ALL_PROXY:
    assert M.find_existing(game, n) is None, '%s 应已移除' % n

print('\n--- 备份轮数 ---')
print('  ', len(os.listdir(os.path.join(game, '_switcher_backup'))))

shutil.rmtree(td, ignore_errors=True)
print('\nOS2 SIM E2E OK')
