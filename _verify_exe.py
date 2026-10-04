# -*- coding: utf-8 -*-
"""Verify the built one-file exe embeds _splash_audio data and Qt6Multimedia DLL."""
import sys

EXE = sys.argv[1] if len(sys.argv) > 1 else \
    "E:/Illusion/RapeLay/_switcher_src/dist/Illusion老游戏修复工具.exe"

from PyInstaller.archive.readers import CArchiveReader

arc = CArchiveReader(EXE)
names = []
for e in arc.toc:
    if isinstance(e, bytes):
        names.append(e.decode("utf-8", "ignore"))
    elif isinstance(e, str):
        names.append(e)
    else:
        names.append(str(getattr(e, "name", e)))

blob = "\n".join(names)
found_audio = "_splash_audio" in blob
found_dll = ("Qt6Multimedia" in blob) or ("Qt6Multimedia.dll" in blob)
found_qtm = ("PySide6/QtMultimedia" in blob) or ("PySide6\\QtMultimedia" in blob)
print("PKG top-level entries:", len(names))
print("contains _splash_audio data:", found_audio)
print("contains Qt6Multimedia DLL:", found_dll)
print("contains PySide6.QtMultimedia module:", found_qtm)
for n in names:
    if "splash" in n.lower() or "Qt6Multimedia" in n:
        print("  MATCH:", n)
ok = found_audio and (found_dll or found_qtm)
print("RESULT:", "OK" if ok else "MISSING")
sys.exit(0 if ok else 1)
