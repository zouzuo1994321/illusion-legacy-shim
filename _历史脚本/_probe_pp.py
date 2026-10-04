# -*- coding: utf-8 -*-
"""Probe OS2 .pp packs: list entries, flag audio-like (PCM) content, dump sizes/headers."""
import os
import struct

DATA = "E:/Illusion/OS2/Data"

def parse_pp(path):
    with open(path, "rb") as f:
        data = f.read()
    cnt = struct.unpack_from("<I", data, 0)[0]
    names_off = 4
    # 32-byte null-terminated SJIS filenames
    names = []
    off = names_off
    for i in range(cnt):
        raw = data[off:off+32]
        names.append(raw.split(b"\x00", 1)[0])
        off += 32
    sizes_off = off
    sizes = []
    for i in range(cnt):
        sizes.append(struct.unpack_from("<I", data, sizes_off + i*4)[0])
    data_off = sizes_off + cnt*4
    entries = []
    run = data_off
    for i in range(cnt):
        sz = sizes[i]
        blob = data[run:run+sz]
        entries.append((i, names[i], run, sz, blob))
        run += sz
    return cnt, names, sizes, data_off, entries, len(data)

def looks_pcm(blob):
    """Heuristic: signed 16-bit PCM little-endian with real variance in high byte."""
    if len(blob) < 64:
        return False, 0.0
    n = len(blob) // 2
    if n < 16:
        return False, 0.0
    import statistics
    # sample high bytes (odd indices for LE int16)
    hi = blob[1::2][:4096]
    lo = blob[0::2][:4096]
    if not hi:
        return False, 0.0
    hi_var = max(hi) - min(hi)
    # compute peak amplitude of int16
    peak = 0
    for k in range(0, min(len(blob), 20000) - 1, 2):
        v = struct.unpack_from("<h", blob, k)[0]
        if abs(v) > peak:
            peak = abs(v)
    return hi_var > 30 and peak > 2000, hi_var

def head_hex(blob, n=16):
    return " ".join("%02x" % b for b in blob[:n])

def main():
    targets = ["os_00m.pp", "os_00n.pp", "os_00s.pp", "os_01.pp", "os_02.pp"]
    for t in targets:
        p = os.path.join(DATA, t)
        if not os.path.exists(p):
            print("MISSING", t)
            continue
        cnt, names, sizes, data_off, entries, flen = parse_pp(p)
        print("\n==== %s  (file=%d, count=%d, data_off=%d, last_end=%d ok=%s)" % (
            t, flen, cnt, data_off,
            entries[-1][2]+entries[-1][3] if entries else 0,
            (entries[-1][2]+entries[-1][3] == flen) if entries else False))
        for i, nm, off, sz, blob in entries:
            try:
                nm_s = nm.decode("shift_jis", errors="replace")
            except Exception:
                nm_s = repr(nm)
            is_pcm, hv = looks_pcm(blob)
            tag = "PCM?" if is_pcm else ""
            print("  [%02d] off=%6d sz=%7d  hdr=%s  %s  %s" % (
                i, off, sz, head_hex(blob), tag, nm_s))

if __name__ == "__main__":
    main()
