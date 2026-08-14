@echo off
setlocal
echo [*] Building FlatSat Ground Station CLI binary for Windows...

python -m PyInstaller --version >nul 2>nul
if %errorlevel% neq 0 (
    echo [!] PyInstaller not found. Installing pyinstaller...
    python -m pip install pyinstaller
    if %errorlevel% neq 0 (
        echo [!] Failed to install PyInstaller.
        pause
        exit /b 1
    )
)

python -m PyInstaller --clean flatsat.spec
if %errorlevel% neq 0 (
    echo [!] PyInstaller compilation failed!
    pause
    exit /b %errorlevel%
)

echo [+] Windows build completed successfully!
echo [+] Binary location: dist\flatsat.exe
pause
