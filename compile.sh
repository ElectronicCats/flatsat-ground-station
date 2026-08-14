#!/usr/bin/env bash
set -e

echo "[*] Building FlatSat Ground Station CLI binary using PyInstaller..."

PYTHON_BIN="${PYTHON:-python3}"

if ! "$PYTHON_BIN" -m PyInstaller --version > /dev/null 2>&1; then
    echo "[!] PyInstaller not found. Installing pyinstaller..."
    "$PYTHON_BIN" -m pip install pyinstaller
fi

"$PYTHON_BIN" -m PyInstaller --clean flatsat.spec

echo "[+] Compilation finished successfully!"
echo "[+] Binary output: dist/flatsat"
