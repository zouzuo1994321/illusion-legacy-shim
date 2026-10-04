# -*- coding: utf-8 -*-
"""Dump a .pp pack's contiguous data section to a .mpg and report size."""
import os
import struct
import sys

PP = sys.argv[1]
OUT = sys.argv[2]

with open(PP, "rb") as f:
    data = f.read()
cnt = struct.unpack_from("<I", data, 0)[0]
off = 4 + cnt * 32
sizes = [struct.unpack_from("<I", data, off + i*4)[0] for i in range(cnt)]
data_off = off + cnt * 4
run = data_off
last = run
for sz in sizes:
    last = run + sz
    run += sz
section = data[data_off:last]
with open(OUT, "wb") as f:
    f.write(section)
print("cnt=%d data_off=%d section_bytes=%d trailing=%d" % (
    cnt, data_off, len(section), len(data) - last))
print("wrote", OUT)
