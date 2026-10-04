# -*- coding: utf-8 -*-
"""离屏冒烟：验证 4 个面板 + 大小写兼容 + 自定义记忆。"""
import os
import sys

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import main as M

print('=' * 62)
print('1) 配置检查')
print('   COMPAT_FLAG =', M.COMPAT_FLAG)
print('   面板数 =', len(M.GAMES))
for g in M.GAMES:
    print('   [%s] %s' % (g['key'], g['display']))

print('\n2) 构建 UI（离屏）')
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)
w = M.MainWindow()
w.show()
app.processEvents()
print('   窗口 = %dx%d  最小 = %dx%d' % (
    w.width(), w.height(), w.minimumSize().width(), w.minimumSize().height()))
print('   标签数 =', w.tabs.count())
for i in range(w.tabs.count()):
    print('     tab[%d] = %s' % (i, w.tabs.tabText(i)))

print('\n3) 各面板定位情况')
for k, tw in w.tab_widgets.items():
    print('   [%s] %s' % (k, tw.spec['display']))
    print('       game_dir =', tw.game_dir)
    print('       exe_path =', tw.exe_path)
    print('       方案 =', M.detect_plan(tw.game_dir) if tw.game_dir else 'N/A')
    if tw.exe_path:
        print('       兼容性 =', repr(M.read_compat(tw.exe_path)))

print('\n4) 自定义程序记忆功能')
cfg = M._cfg_path()
print('   配置路径 =', cfg)
print('   load_custom() =', repr(M.load_custom()))
M.save_custom(r'D:\test\demo.exe')
print('   写入后 load_custom() =', repr(M.load_custom()))
M.save_custom('')
print('   清空后 load_custom() =', repr(M.load_custom()))

print('\n5) 大小写不敏感查找')
os2_dir = r'E:\Illusion\OS2'
if os.path.isdir(os2_dir):
    print('   OS2 目录存在')
    for n in ['d3d9.dll', 'D3D9.dll', 'ddraw.dll', 'DDraw.dll']:
        p = M.find_existing(os2_dir, n)
        print('     查找 %-12s → %s' % (n, os.path.basename(p) if p else None))
    print('   detect_plan(OS2) =', M.detect_plan(os2_dir))
    print('   scan_files(OS2) =', [x[0] for x in M.scan_files(os2_dir)])

print('\n6) 布局高度一致性')
hs = [tw.height() for tw in w.tab_widgets.values()]
print('   各 tab 高度:', hs)
print('   一致 =', len(set(hs)) == 1)

print('\n' + '=' * 62)
print('SMOKE OK')
