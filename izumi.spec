# -*- mode: python ; coding: utf-8 -*-

import glob
import sys
from pathlib import Path

# Find libclang dynamically — path differs between Linux (.so) and Windows (.dll)
_libclang = next(
    (p for p in glob.glob(".venv/**/libclang.*", recursive=True)
     if Path(p).suffix in (".so", ".dll")),
    None,
)
_binaries = [(_libclang, "clang/native")] if _libclang else []

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=_binaries,
    datas=[
        ("i18n/en.json", "i18n"),
        ("i18n/ja.json", "i18n"),
    ],
    hiddenimports=[
        # clang is imported inside try/except so PyInstaller misses it
        "clang",
        "clang.cindex",
        "clang.enumerations",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='izumi',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    # console=True: needed for CLI output to be visible on Windows
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='izumi',
)
