# -*- coding: utf-8 -*-
"""
端到端验证（不启动游戏，只验证部署链路）：
- 模拟：在临时游戏目录里放一个假 exe，走 ensure_plans_extracted + deploy 全流程
- 验证方案A/B/0 切换后文件状态是否符合预期
"""
import os
import sys
import shutil
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main as M

LOGS = []
def log(m, *a):
    if a:
        try:
            m = m % a
        except Exception:
            pass
    LOGS.append(m)

# 1) 准备一个模拟游戏目录
tmp_root = tempfile.mkdtemp(prefix='e2e_root_')
game_dir = os.path.join(tmp_root, 'FakeGame')
os.makedirs(os.path.join(game_dir, '[特典包BotuPlay]'), exist_ok=True)
open(os.path.join(game_dir, 'RapeLay_cn.exe'), 'wb').write(b'MZ fake')
open(os.path.join(game_dir, '[特典包BotuPlay]', 'BotuPlay.exe'), 'wb').write(b'MZ fake')

print('模拟根目录:', tmp_root)
ok, msg = M.ensure_plans_extracted(tmp_root, log=log)
print('释放方案:', ok, msg)
src = M.plans_root(tmp_root)

def state(d):
    return sorted(n for n in os.listdir(d) if n.lower() in
                  [x.lower() for x in M.PLAN_FILES] or n.endswith('.off'))

print('\n--- 部署方案A ---')
ok, msg = M.deploy(game_dir, 'A', src, log)
print(ok, msg, '| 检测 =', M.detect_plan(game_dir))
print('  文件:', state(game_dir))

print('\n--- 部署方案B（A→B 切换，应移除 dxgi/d3d11/d3d10core，停用 dxvk.conf）---')
ok, msg = M.deploy(game_dir, 'B', src, log)
print(ok, msg, '| 检测 =', M.detect_plan(game_dir))
print('  文件:', state(game_dir))
assert not os.path.exists(os.path.join(game_dir, 'dxgi.dll')), 'A 的 dxgi.dll 应被移除'
assert os.path.exists(os.path.join(game_dir, 'ddraw.dll')), 'B 的 ddraw.dll 应存在'
assert os.path.exists(os.path.join(game_dir, 'dxvk.conf.off')), 'dxvk.conf 应被停用'
print('  ✔ A→B 切换正确')

print('\n--- 部署方案0（全清）---')
ok, msg = M.deploy(game_dir, '0', src, log)
print(ok, msg, '| 检测 =', M.detect_plan(game_dir))
print('  文件:', state(game_dir))
for n in M.ALL_PROXY:
    assert not os.path.exists(os.path.join(game_dir, n)), '%s 应被移除' % n
print('  ✔ 方案0 清理正确')

print('\n--- 部署方案A（0→A 回归）---')
ok, msg = M.deploy(game_dir, 'A', src, log)
print(ok, msg, '| 检测 =', M.detect_plan(game_dir))
print('  文件:', state(game_dir))
assert os.path.exists(os.path.join(game_dir, 'd3d9.dll'))
assert os.path.exists(os.path.join(game_dir, 'dxvk.conf')), 'dxvk.conf 应被恢复'
print('  ✔ 0→A 回归正确')

print('\n--- 备份目录 ---')
bk = os.path.join(game_dir, '_switcher_backup')
print('  备份轮数 =', len(os.listdir(bk)) if os.path.isdir(bk) else 0)

shutil.rmtree(tmp_root, ignore_errors=True)
print('\nE2E OK')
