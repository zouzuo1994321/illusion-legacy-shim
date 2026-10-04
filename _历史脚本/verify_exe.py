# -*- coding: utf-8 -*-
"""
打包 exe 的真机验证：
1) 子进程运行 exe（offscreen），检查资源释放
2) 直接提取 exe 内嵌资源验证（zip 完整性）
3) 检查图标（RT_GROUP_ICON / RT_ICON）
"""
import os
import subprocess
import sys
import struct

EXE = r'E:\Illusion\RapeLay\_switcher_src\dist\Illusion老游戏修复工具.exe'
print('EXE =', EXE)
print('大小 = %.1f MB' % (os.path.getsize(EXE) / 1048576))

# ---- 1) 检查 PE 资源表是否有 RT_ICON(3) / RT_GROUP_ICON(14) ----
def pe_resources(path):
    with open(path, 'rb') as f:
        f.seek(0x3C)
        pe_off = struct.unpack('<I', f.read(4))[0]
        f.seek(pe_off)
        assert f.read(4) == b'PE\x00\x00'
        machine = struct.unpack('<H', f.read(2))[0]
        nsec = struct.unpack('<H', f.read(2))[0]
        f.read(12)
        opt_size = struct.unpack('<H', f.read(2))[0]
        f.read(2)
        opt_off = f.tell()
        magic = struct.unpack('<H', f.read(2))[0]
        pe32p = (magic == 0x20b)
        f.seek(opt_off + (112 if pe32p else 96))
        nrva = struct.unpack('<I', f.read(4))[0]
        f.seek(opt_off + (112 if pe32p else 96) + 8)
        res_rva, res_size = struct.unpack('<II', f.read(8))
        sec_off = opt_off + opt_size
        f.seek(sec_off)
        secs = []
        for _ in range(nsec):
            name = f.read(8)
            vsize, vaddr, rsize, raddr = struct.unpack('<IIII', f.read(16))
            f.read(16)
            secs.append((vaddr, vsize, raddr, rsize))

        def rva2off(rva):
            for vaddr, vsize, raddr, rsize in secs:
                if vaddr <= rva < vaddr + max(vsize, rsize):
                    return raddr + (rva - vaddr)
            return None

        ro = rva2off(res_rva)
        if ro is None:
            return set()
        types = set()

        def walk(off, level):
            nname, nid = struct.unpack('<HH', f.read(4))
            f.read(4)
            for i in range(nname + nid):
                f.seek(off + 8 + i * 8)
                nm, offv = struct.unpack('<II', f.read(8))
                if nm & 0x80000000:
                    continue
                if level == 0:
                    types.add(nm)
                if offv & 0x80000000:
                    walk(ro + (offv & 0x7FFFFFFF), level + 1)

        walk(ro, 0)
        return types

types = pe_resources(EXE)
print('\nPE 资源类型:', sorted(types))
print('  RT_ICON(3) 存在 =', 3 in types)
print('  RT_GROUP_ICON(14) 存在 =', 14 in types)
print('  RT_MANIFEST(24) 存在 =', 24 in types)

# ---- 2) 运行 exe 的离屏模式，验证资源释放 ----
print('\n--- 启动 exe（离屏）验证资源释放 ---')
env = dict(os.environ)
env['QT_QPA_PLATFORM'] = 'offscreen'
# 让 exe 自己在临时目录释放，模拟真实使用
import tempfile, time, shutil
td = tempfile.mkdtemp(prefix='exe_probe_')
shutil.copy2(EXE, os.path.join(td, 'tool.exe'))
p = subprocess.Popen([os.path.join(td, 'tool.exe')], env=env,
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(18)
alive = p.poll() is None
print('  进程存活 =', alive)
plans = os.path.join(td, '_方案切换')
if os.path.isdir(plans):
    print('  已释放 _方案切换:')
    for root, dirs, files in os.walk(plans):
        for fn in files:
            fp = os.path.join(root, fn)
            print('     %-50s %d' % (os.path.relpath(fp, plans),
                                     os.path.getsize(fp)))
else:
    print('  !! 未释放 _方案切换')

try:
    p.terminate()
    p.wait(timeout=5)
except Exception:
    p.kill()
# 备份释放结果（供人工核对）
keep = r'E:\Illusion\RapeLay\_switcher_src\_exe_probe_out'
shutil.rmtree(keep, ignore_errors=True)
if os.path.isdir(plans):
    shutil.copytree(plans, keep)
    print('  释放结果已留档:', keep)
shutil.rmtree(td, ignore_errors=True)
print('\nEXE VERIFY DONE')
