# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Illusion老游戏修复工具 v3.10"""

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('logo.ico', '.'),
        ('logo_big.png', '.'),
        ('logo.png', '.'),
        ('logo_splash.png', '.'),
        ('logo_illusion.png', '.'),
        ('_plans.zip', '.'),
        ('_dx', '_dx'),
        ('_social', '_social'),
        ('_splash_audio', '_splash_audio'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy',
        'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
        'PySide6.Qt3DCore', 'PySide6.QtQml',
        'PySide6.QtQuick', 'PySide6.QtSql', 'PySide6.QtTest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Illusion老游戏修复工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='logo.ico',
)
