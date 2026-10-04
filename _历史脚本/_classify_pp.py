# -*- coding: utf-8 -*-
"""Classify .pp entries: WAV / MP2-MP3 / PCM16 / other. Report audio candidates."""
import os
import struct
import sys

DATA = "E:/Illusion/OS2/Data"

def parse_pp(path):
    with open(path, "rb") as f:
        data = f.read()
    cnt = struct.unpack_from("<I", data, 0)[0]
    off = 4 + cnt * 32
    sizes = [struct.unpack_from("<I", data, off + i*4)[0] for i in range(cnt)]
    data_off = off + cnt * 4
    entries = []
    run = data_off
    for i in range(cnt):
        sz = sizes[i]
        entries.append((i, run, sz, data[run:run+sz]))
        run += sz
    return cnt, entries, len(data)

def classify(blob):
    n = len(blob)
    if n < 32:
        return "tiny"
    if blob[:4] == b"RIFF":
        return "WAV"
    # MPEG audio frame sync: 0xFF 0xF_ / 0xFF 0xE_  (11-bit)
    if blob[0] == 0xFF and (blob[1] & 0xE0) == 0xE0:
        return "MPx"
    # PCM16 smoothness test on first ~4000 samples
    m = min(n, 16000) - 1
    if m < 30:
        return "other"
    peak = 0
    smooth = 0
    total = 0
    prev = struct.unpack_from("<h", blob, 0)[0]
    for k in range(2, m, 2):
        v = struct.unpack_from("<h", blob, k)[0]
        if abs(v) > peak:
            peak = abs(v)
        if abs(v - prev) < 6000:
            smooth += 1
        total += 1
        prev = v
    if peak < 2000:
        return "other"
    ratio = smooth / total if total else 0
    if ratio > 0.55:
        return "PCM16"
    return "other"

def main():
    for t in ["os_01.pp", "os_02.pp", "os_00m.pp", "os_00n.pp", "os_00s.pp"]:
        p = os.path.join(DATA, t)
        cnt, entries, flen = parse_pp(p)
        print("\n==== %s  file=%d count=%d" % (t, flen, cnt))
        acount = {"WAV":0,"MPx":0,"PCM16":0,"other":0,"tiny":0}
        for i, off, sz, blob in entries:
            c = classify(blob)
            acount[c] = acount.get(c, 0) + 1
            if c in ("WAV", "MPx", "PCM16"):
                dur = sz / 2 / 44100.0  # assume 44100 mono 16-bit
                print("  [%02d] sz=%8d  %-6s  ~%.1fs" % (i, sz, c, dur))
        print("  summary:", acount)

if __name__ == "__main__":
    main()
