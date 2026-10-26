# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the self-contained FlatSat Ground Station app.

Produces a single ``flatsat-gs`` executable with Python, Flask, SocketIO,
pyserial, click, rich and pycryptodome bundled inside, so users can run the
dashboard and the CLI without installing Python, without pip and without
Docker:

    flatsat-gs            -> dashboard web (abre el navegador)
    flatsat-gs cli        -> CLI interactivo
    flatsat-gs doctor     -> diagnóstico
    flatsat-gs install    -> instala en el perfil del usuario

    Linux/macOS : ./compile_app.sh
    Windows     : build_app_windows.bat
"""

import os

from PyInstaller.utils.hooks import collect_all, collect_data_files

# ── Data files ──────────────────────────────────────────────────────────────
# Flask resolves templates/ relative to the module directory, which under
# PyInstaller lives inside the bundle: keep the same layout.
datas = [('VERSION', '.'), ('requirements-app.txt', '.')]
datas += collect_data_files(
    'modules.webapp',
    includes=['templates/**/*', 'static/**/*', '*.txt', 'logs/**/*'],
)

# ── Icon ────────────────────────────────────────────────────────────────────
icon_path = os.path.join(os.path.abspath('.'), 'assets', 'flatsat-gs.ico')
icon = icon_path if os.path.exists(icon_path) else None

binaries = []
hiddenimports = [
    'modules',
    'modules.core',
    'modules.core.ccsds',
    'modules.core.cli',
    'modules.core.device',
    'modules.core.radio_bridge',
    'modules.core.serial_manager',
    'modules.core.session',
    'modules.core.shell_parser',
    'modules.core.state',
    'modules.core.telecommand',
    'modules.core.telemetry',
    'modules.utils',
    'modules.utils.bootstrap',
    'modules.utils.installer',
    'modules.utils.serial_doctor',
    'modules.webapp',
    'modules.webapp.app',
    'modules.webapp.auth',
    'modules.webapp.config',
    'modules.webapp.db',
    'modules.webapp.radio_bridge',
    'modules.webapp.seed',
    # Web stack
    'flask',
    'flask_socketio',
    'socketio',
    'engineio',
    'simple_websocket',
    'jinja2',
    'werkzeug',
    'itsdangerous',
    'click',
    # CLI
    'rich',
    # Hardware
    'serial',
    'serial.tools.list_ports',
    'serial.tools.list_ports_windows',
    'serial.tools.list_ports_posix',
    'serial.tools.list_ports_linux',
    'serial.tools.list_ports_osx',
    # engineio/socketio pick the async driver with a dynamic
    # importlib.import_module('engineio.async_drivers.' + mode), which
    # PyInstaller cannot detect. Without these the frozen app raises
    # "Invalid async_mode specified" at startup.
    'engineio.async_drivers.threading',
    'socketio.async_drivers.threading',
]

for package in ['Crypto']:
    tmp_ret = collect_all(package)
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]

a = Analysis(
    ['flatsat_app.py'],
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

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='flatsat-gs',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
)
