# -*- coding: utf-8 -*-
"""
OS2 大小写端到端测试（在真实 OS2 目录操作，但会先备份并可完整恢复）。
验证：大写 D3D9.dll 环境下，切到方案A 不会留下两份 dll。
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main as M

OS2 = r'E:\Illusion\OS2'
SRC = r'E:\Illusion\RapeLay\_方案切换'
LOGS = []
def log(m, *a):
    if a:
        try:
            m = m % a
        except Exception:
            pass
    LOGS.append(m)

print('=' * 62)
print('OS2 大小写 E2E 测试（真实目录，测试后恢复）')
print('=' * 62)

def listing():
    out = {}
    for f in os.listdir(OS2):
        low = f.lower()
        if low in [x.lower() for x in M.PLAN_FILES]:
            out[low] = f
    return out

# 记录初始状态
init = listing()
print('\n[初始] 代理文件:', init)
init_backup = os.path.join(OS2, '_switcher_backup', '20261004_初始dgVoodoo状态')
print('[初始] 已有备份目录:', os.path.isdir(init_backup))

# --- 切到方案A ---
print('\n--- 部署方案A（DXVK）于大写环境 ---')
ok, msg = M.deploy(OS2, 'A', SRC, log)
print('  ', ok, msg)
cur = listing()
print('  当前文件:', cur)
# 关键断言：不能同时存在 d3d9.dll 和 D3D9.dll
names = list(cur.values())
lows = [n.lower() for n in names]
assert len(lows) == len(set(lows)), '存在同名不同大小写的重复文件！%s' % names
print('  ✔ 无重复大小写文件')
print('  检测方案 =', M.detect_plan(OS2))

# --- 切到方案B ---
print('\n--- 部署方案B（dgVoodoo）---')
ok, msg = M.deploy(OS2, 'B', SRC, log)
print('  ', ok, msg)
cur = listing()
print('  当前文件:', cur)
lows = [n.lower() for n in cur.values()]
assert len(lows) == len(set(lows)), '存在重复！%s' % list(cur.values())
print('  ✔ 无重复大小写文件')
print('  检测方案 =', M.detect_plan(OS2))

# --- 恢复到初始 dgVoodoo 状态 ---
print('\n--- 恢复到初始状态（从备份）---')
if os.path.isdir(init_backup):
    # 先清掉方案A/B 放入的（小写）文件
    for low in list(M.ALL_PROXY) + list(M.ALL_CONF) + ['dgvoodoocpl.exe']:
        p = M.find_existing(OS2, low)
        if p and os.path.basename(p) not in ('D3D8.dll','D3D9.dll','D3DImm.dll','DDraw.dll',
                                             'dgVoodoo.conf','dgVoodooCpl.exe'):
            os.remove(p)
            print('   清理:', os.path.basename(p))
    # 清理 .off
    for f in os.listdir(OS2):
        if f.endswith('.off'):
            os.rename(os.path.join(OS2, f), os.path.join(OS2, f[:-4]))
            print('   恢复:', f)
    print('   最终:', listing())
    print('   检测方案 =', M.detect_plan(OS2))

print('\n' + '=' * 62)
print('OS2 E2E OK')
