# -*- coding: utf-8 -*-
"""列出回收站中含 _switcher_src 或 main.py 或 logo 的全部条目。"""
import os
import struct
import glob

BIN = r'E:\$Recycle.Bin\S-1-5-21-3385280145-2370340941-1411040773-1001'


def parse_i(path):
    with open(path, 'rb') as f:
        data = f.read()
    if len(data) < 28:
        return None
    ver = struct.unpack('<Q', data[0:8])[0]
    size = struct.unpack('<Q', data[8:16])[0]
    nlen = struct.unpack('<I', data[24:28])[0]
    name = data[28:28 + nlen * 2].decode('utf-16-le', 'replace').rstrip('\x00')
    return ver, size, name


rows = []
for p in glob.glob(os.path.join(BIN, '$I*')):
    try:
        r = parse_i(p)
    except Exception:
        continue
    if not r:
        continue
    ver, size, name = r
    rows.append((name, size, p))

# 精确过滤：只要 _switcher_src 下的一级文件 / main.py / logo* / verify*
sel = []
for name, size, ip in rows:
    n = name.replace('/', '\\')
    tail = n.split('\\')[-1]
    is_sw = '_switcher_src' in n
    is_key = tail.lower() in ('main.py', 'logo.ico', 'logo_big.png', 'logo.png',
                              'verify_launch.py', 'verify.py') or \
             tail.lower().startswith('verify') or tail.lower().startswith('logo')
    # 排除 build/dist 内部
    if '\\build\\' in n or '\\dist\\' in n:
        continue
    if is_sw or is_key:
        sel.append((name, size, ip))

sel.sort(key=lambda x: x[0])
print('共 %d 项：' % len(sel))
for name, size, ip in sel:
    rp = ip.replace('\\$I', '\\$R')
    print('%-14d %s' % (size, name))
    print('      $R=%s  存在=%s' % (os.path.basename(rp), os.path.exists(rp)))
