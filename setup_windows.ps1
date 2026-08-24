# Setup Script for Windows Users
# Automates the creation of global shortcuts (flatsat, flatsat-web, and optional flatsat-tui)

$GsDir = Get-Item -LiteralPath $PSScriptRoot
$ParentDir = $GsDir.Parent.FullName
$TuiDir = Join-Path $ParentDir "flat-sat-fw-interno"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "FlatSat Ground Station Windows Auto-Setup" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Ground Station path: $($GsDir.FullName)" -ForegroundColor Yellow

# Create PowerShell Profile directory if it doesn't exist
$ProfileDir = Split-Path $PROFILE
if (-not (Test-Path -LiteralPath $ProfileDir)) {
    New-Item -ItemType Directory -Path $ProfileDir -Force | Out-Null
}

# Create Profile file if it doesn't exist
if (-not (Test-Path -LiteralPath $PROFILE)) {
    New-Item -ItemType File -Path $PROFILE -Force | Out-Null
}

$gs_path = $GsDir.FullName
$tui_path = if (Test-Path -LiteralPath $TuiDir) { $TuiDir } else { "" }

# Code block to append
$CodeBlock = @"

# --- FlatSat Global Shortcuts (Auto-generated) ---
`$GS_DIR = "$gs_path"
`$TUI_DIR = "$tui_path"

function flatsat {
    `$cli_path = "`$GS_DIR\flatsat.py"
    `$python_path = "`$GS_DIR\.venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath "`$python_path")) {
        `$python_path = "python"
    }
    if (Test-Path -LiteralPath "`$cli_path") {
        & `$python_path "`$cli_path" `@args
    } else {
        Write-Host "Error: No se encontro flatsat.py en `$cli_path" -ForegroundColor Red
    }
}

function flatsat-web {
    `$python_path = "`$GS_DIR\.venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath "`$python_path")) {
        `$python_path = "python"
    }
    if (Test-Path -LiteralPath "`$GS_DIR\webapp") {
        Set-Location -LiteralPath "`$GS_DIR"
        & `$python_path -m webapp.app `@args
    } else {
        Write-Host "Error: No se encontro la carpeta webapp en `$GS_DIR" -ForegroundColor Red
    }
}

if (`$TUI_DIR -and (Test-Path -LiteralPath "`$TUI_DIR\flatsatTUI")) {
    function flatsat-tui {
        `$python_path = "`$TUI_DIR\.venv\Scripts\python.exe"
        if (-not (Test-Path -LiteralPath "`$python_path")) {
            `$python_path = "python"
        }
        Set-Location -LiteralPath "`$TUI_DIR"
        & `$python_path -m flatsatTUI `@args
    }
}
Write-Host "🚀 Atajos de FlatSat cargados exitosamente (flatsat, flatsat-web)" -ForegroundColor Green
# --- End FlatSat Global Shortcuts ---
"@

# Read current profile content to avoid duplicate injection
$CurrentContent = ""
if (Test-Path -LiteralPath $PROFILE) {
    $CurrentContent = Get-Content -LiteralPath $PROFILE -Raw
}

if ($CurrentContent -like "*FlatSat Global Shortcuts (Auto-generated)*") {
    Write-Host "[*] Profile already contains FlatSat shortcuts. Updating paths..." -ForegroundColor Yellow
    # Remove old block and append new
    $CleanContent = $CurrentContent -replace "(?s)# --- FlatSat Global Shortcuts \(Auto-generated\) ---.*?# --- End FlatSat Global Shortcuts ---", ""
    $CleanContent.Trim() + "`r`n`r`n" + $CodeBlock | Out-File -FilePath $PROFILE -Encoding utf8
} else {
    Write-Host "[+] Injecting shortcuts into profile..." -ForegroundColor Green
    Add-Content -Path $PROFILE -Value "`r`n$CodeBlock" -Encoding utf8
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "[+] SUCCESS! Windows shortcuts configured successfully." -ForegroundColor Green
Write-Host "Please restart your PowerShell terminal or run:" -ForegroundColor Yellow
Write-Host "  . `$PROFILE" -ForegroundColor White
Write-Host "==========================================" -ForegroundColor Cyan
