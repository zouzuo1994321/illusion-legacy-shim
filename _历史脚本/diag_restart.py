# -*- coding: utf-8 -*-
"""观察 BotuPlay 是否在反复重启（PID 变化 = 崩溃重启循环）。"""
import subprocess
import time

def procs():
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq BotuPlay.exe', '/FO', 'CSV', '/NH'],
                       capture_output=True)
    o = r.stdout.decode('gbk', 'ignore').strip()
    out = []
    if 'BotuPlay' not in o:
        return out
    for line in o.splitlines():
        line = line.strip()
        if not line:
            continue
        p = [x.strip('"') for x in line.split('","')]
        if len(p) >= 5:
            out.append((p[1], p[4]))
    return out


subprocess.run(['cmd', '/c', 'explorer.exe', r'E:\Illusion\RapeLay\[特典包BotuPlay]\BotuPlay.exe'],
               capture_output=True)

seen = []
print('t  | PID/mem')
for t in range(1, 61):
    time.sleep(1)
    ps = procs()
    if ps:
        tag = ' '.join('%s/%s' % x for x in ps)
    else:
        tag = '---'
    print('t=%02d | %s' % (t, tag))
    seen.append((t, tuple(x[0] for x in ps)))

pids = []
for t, plist in seen:
    for p in plist:
        if p not in pids:
            pids.append(p)
print('\n出现过的 PID 序列:', pids)
print('PID 变化次数:', len(pids) - 1, '=> 若 >0 说明发生了重启')

subprocess.run(['taskkill', '/F', '/IM', 'BotuPlay.exe'], capture_output=True)
