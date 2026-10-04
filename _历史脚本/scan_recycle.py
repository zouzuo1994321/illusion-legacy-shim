# -*- coding: utf-8 -*-
"""解析 E: 回收站的 $I 元数据文件，找出含关键字的被删文件及其 $R 实体。"""
import os
import struct
import glob

BIN = r'E:\$Recycle.Bin\S-1-5-21-3385280145-2370340941-1411040773-1001'
KEYS = ['main.py', 'switcher', '方案切换', 'logo', '历史版本', '修复工具', '_方案', 'verify_', 'icon']


def parse_i(path):
    """$I 文件：8字节头 + 8字节大小 + 8字节时间 + 4字节名长 + 名称(UTF-16LE)"""
    with open(path, 'rb') as f:
        data = f.read()
    if len(data) < 28:
        return None
    ver = struct.unpack('<Q', data[0:8])[0]
    size = struct.unpack('<Q', data[8:16])[0]
    ftime = struct.unpack('<Q', data[16:24])[0]
    if ver == 2:
        nlen = struct.unpack('<I', data[24:28])[0]
        name = data[28:28 + nlen * 2].decode('utf-16-le', 'replace').rstrip('\x00')
    else:  # ver 1
        nlen = struct.unpack('<I', data[24:28])[0]
        name = data[28:28 + nlen].decode('utf-16-le', 'replace').rstrip('\x00')
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
    low = name.lower()
    if any(k.lower() in low for k in KEYS):
        rp = p.replace('\\$I', '\\$R')
        exists = os.path.exists(rp)
        rows.append((name, size, ver, p, rp, exists))

rows.sort(key=lambda x: x[0])
print('命中 %d 项：' % len(rows))
for name, size, ver, ip, rp, ex in rows:
    print('  [%s] size=%-12d ver=%d' % ('R存在' if ex else 'R缺失', size, ver))
    print('      原名: %s' % name)
    print('      $I: %s' % os.path.basename(ip))
    print('      $R: %s' % os.path.basename(rp))
