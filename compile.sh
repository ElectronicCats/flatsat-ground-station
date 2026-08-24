#!/usr/bin/env bash
set -e

echo "[*] Building FlatSat Ground Station CLI binary using PyInstaller..."

if [ -z "$PYTHON" ]; then
    if [ -f ".venv/bin/python" ]; then
        PYTHON=".venv/bin/python"
    else
        PYTHON="python3"
    fi
fi

if ! "$PYTHON" -m PyInstaller --version > /dev/null 2>&1; then
    echo "[!] PyInstaller not found. Installing pyinstaller..."
    "$PYTHON" -m pip install pyinstaller
fi

"$PYTHON" -m PyInstaller --clean flatsat.spec

echo "[+] Compilation finished successfully!"
echo "[+] Binary output: dist/flatsat"
