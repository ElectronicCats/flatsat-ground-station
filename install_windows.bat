@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo   FlatSat Ground Station - Windows Auto-Installer
echo ===================================================
echo.

REM 1. Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] ERROR: Python is not installed or not added to system PATH.
    echo [!] Please install Python 3.9+ from https://www.python.org/
    echo [!] Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

echo [*] Python detected. Setting up virtual environment...

REM 2. Create Virtual Environment (.venv) if it doesn't exist
if not exist ".venv" (
    echo [*] Creating virtual environment (.venv)...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [!] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

REM 3. Install package in editable mode
echo [*] Installing FlatSat CLI package and dependencies...
.venv\Scripts\python.exe -m pip install --upgrade pip >nul 2>&1
.venv\Scripts\python.exe -m pip install -e .
if %errorlevel% neq 0 (
    echo [!] Package installation failed.
    pause
    exit /b 1
)

REM 4. Create batch wrappers for CMD / PowerShell in WindowsApps (pre-added to PATH)
set "USER_APPS=%LOCALAPPDATA%\Microsoft\WindowsApps"

if exist "%USER_APPS%" (
    echo [*] Registering 'flatsat' global alias in WindowsApps...
    (
        echo @echo off
        echo "%~dp0.venv\Scripts\python.exe" "%~dp0flatsat.py" %%*
    ) > "%USER_APPS%\flatsat.bat"
    
    (
        echo @echo off
        echo "%~dp0.venv\Scripts\python.exe" -m webapp.app %%*
    ) > "%USER_APPS%\flatsat-web.bat"
    
    echo [+] Global alias 'flatsat' registered to PATH.
) else (
    echo [*] Registering local batch launcher...
    (
        echo @echo off
        echo "%~dp0.venv\Scripts\python.exe" "%~dp0flatsat.py" %%*
    ) > "%~dp0flatsat_cmd.bat"
)

REM 5. Configure PowerShell Profile shortcuts bypassing ExecutionPolicy restrictions
if exist "%~dp0setup_windows.ps1" (
    echo [*] Setting up PowerShell Profile aliases...
    powershell.exe -ExecutionPolicy Bypass -File "%~dp0setup_windows.ps1" >nul 2>&1
)

echo.
echo ===================================================
echo [+] SUCCESS! FlatSat Ground Station is ready to use.
echo ===================================================
echo.
echo Available commands in CMD and PowerShell:
echo   - flatsat           : Open FlatSat CLI help
echo   - flatsat devices   : List connected FlatSat boards
echo   - flatsat status    : Read system status from board
echo   - flatsat-web       : Launch Web Dashboard
echo.
pause
