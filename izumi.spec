# -*- mode: python ; coding: utf-8 -*-

import glob
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, copy_metadata

# Bundle all of litellm and tiktoken to avoid hidden-import/data-file issues
_litellm_datas, _litellm_binaries, _litellm_hiddenimports = collect_all("litellm")
_tiktoken_datas, _tiktoken_binaries, _tiktoken_hiddenimports = collect_all("tiktoken")
_tiktoken_ext_datas, _tiktoken_ext_binaries, _tiktoken_ext_hiddenimports = collect_all("tiktoken_ext")
# tiktoken discovers encodings via importlib.metadata entry points; copy metadata so plugins are found
_tiktoken_meta = copy_metadata("tiktoken")

# Find libclang dynamically — path differs between Linux (.so) and Windows (.dll)
_libclang = next(
    (p for p in glob.glob(".venv/**/libclang.*", recursive=True)
     if Path(p).suffix in (".so", ".dll")),
    None,
)
_binaries = (
    [(_libclang, "clang/native"), *_litellm_binaries, *_tiktoken_binaries, *_tiktoken_ext_binaries]
    if _libclang else
    [*_litellm_binaries, *_tiktoken_binaries, *_tiktoken_ext_binaries]
)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=_binaries,
    datas=[
        ("i18n/en.json", "i18n"),
        ("i18n/ja.json", "i18n"),
        *_litellm_datas,
        *_tiktoken_datas,
        *_tiktoken_ext_datas,
        *_tiktoken_meta,
    ],
    hiddenimports=[
        # clang is imported inside try/except so PyInstaller misses it
        "clang",
        "clang.cindex",
        "clang.enumerations",
        # tiktoken encoding plugins are discovered via entry points
        "tiktoken_ext",
        "tiktoken_ext.openai_public",
        *_litellm_hiddenimports,
        *_tiktoken_hiddenimports,
        *_tiktoken_ext_hiddenimports,
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
