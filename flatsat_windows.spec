# flatsat_windows.spec
# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_all

datas = [('VERSION', '.')]
binaries = []
hiddenimports = [
    'click',
    'serial',
    'serial.tools.list_ports',
    'serial.tools.list_ports_windows',
    'win32file',
    'win32pipe',
    'win32event',
    'win32security',
    'win32api',
    'pywintypes',
    'modules',
    'modules.core',
    'modules.webapp',
    'modules.utils',
    'core',
    'cli',
    'webapp',
]

for package in ['rich', 'requests', 'Crypto']:
    tmp_ret = collect_all(package)
    datas.extend(tmp_ret[0])
    binaries.extend(tmp_ret[1])
    hiddenimports.extend(tmp_ret[2])

extra_files = [
    ('README.md', '.'),
    ('LICENSE', '.'),
]

for src, dst in extra_files:
    if os.path.exists(src):
        datas.append((src, dst))

a = Analysis(
    ['flatsat.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'pytest_flask', 'tkinter', 'unittest'],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe_flatsat = EXE(
    pyz,
    a.scripts,
    [('flatsat.py', 'flatsat', 'PYMODULE')],
    exclude_binaries=True,
    name='flatsat',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None
)

coll = COLLECT(
    exe_flatsat,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='flatsat',
)
