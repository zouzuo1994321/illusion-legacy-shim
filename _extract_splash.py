# -*- coding: utf-8 -*-
"""Extract 3 authentic OS2 startup-jingle candidates from os_02.pp (clean PCM16),
wrap as 44100Hz mono 16-bit WAV, write into _splash_audio/.

Selection: prefer musical (low zero-crossing rate) jingles of length 0.9-2.6s,
so they pair naturally with the ~1.5s logo fade.
"""
import os
import struct
import json
import wave

BASE = "E:/Illusion/RapeLay/_switcher_src"
PP = "E:/Illusion/OS2/Data/os_02.pp"
OUT = os.path.join(BASE, "_splash_audio")
SR = 44100

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
    return entries

def looks_pcm16(blob):
    if len(blob) < 64:
        return False
    peak = 0
    smooth = 0
    total = 0
    prev = struct.unpack_from("<h", blob, 0)[0]
    for k in range(2, min(len(blob), 16000) - 1, 2):
        v = struct.unpack_from("<h", blob, k)[0]
        if abs(v) > peak:
            peak = abs(v)
        if abs(v - prev) < 6000:
            smooth += 1
        total += 1
        prev = v
    return peak > 2000 and (smooth / total if total else 0) > 0.55

def zcr(blob):
    """Zero-crossing rate of int16 samples (lower = more tonal/musical)."""
    n = len(blob) // 2
    if n < 16:
        return 1.0
    cross = 0
    prev = struct.unpack_from("<h", blob, 0)[0]
    for k in range(2, min(len(blob), 60000) - 1, 2):
        v = struct.unpack_from("<h", blob, k)[0]
        if (prev >= 0) != (v >= 0):
            cross += 1
        prev = v
    return cross / max(1, n - 1)

def main():
    entries = parse_pp(PP)
    cands = []
    for i, off, sz, blob in entries:
        if not looks_pcm16(blob):
            continue
        dur = sz / 2 / SR
        if 0.9 <= dur <= 2.6:
            cands.append((i, sz, dur, zcr(blob)))
    cands.sort(key=lambda x: x[3])  # lowest ZCR first = most musical
    print("Musicality-ranked candidates (idx, size, dur, zcr):")
    for c in cands[:12]:
        print("  [%02d] sz=%7d  %.2fs  zcr=%.4f" % c)
    pick = cands[:3]
    os.makedirs(OUT, exist_ok=True)
    written = []
    for i, sz, dur, _z in pick:
        blob = entries[i][3]
        fn = "os2_os02_e%02d.wav" % i
        path = os.path.join(OUT, fn)
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(blob)
        written.append(fn)
        print("wrote", fn, "(%d bytes -> %.2fs @%dHz)" % (len(blob), dur, SR))
    man = {
        "note": "启动音白名单（相对本目录的文件名）。游戏原版「启动画面三种音频随机选一」，这里保留同样行为：每次启动随机取一条。音频为从 波动少女2 的 os_02.pp 资源包中提取的 PCM16 原始音频（采样率按 44100Hz mono 解读），封装为标准 WAV。",
        "sample_rate": SR,
        "channels": 1,
        "files": written,
    }
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=2)
    print("manifest updated:", written)

if __name__ == "__main__":
    main()
