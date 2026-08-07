# Setup Script for Windows Users
# Automates the creation of global shortcuts (flatsat, flatsat-tui, flatsat-web)

$ProjectRoot = Get-Item $PSScriptRoot
$ParentDir = $ProjectRoot.Parent.FullName

# Determine the paths
$flatsat_dir = $ParentDir # Root directory containing flat-sat-fw-interno and flatsat-ground-station

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "FlatSat Windows Environment Auto-Setup" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Detected project path: $flatsat_dir" -ForegroundColor Yellow

# Create PowerShell Profile directory if it doesn't exist
$ProfileDir = Split-Path $PROFILE
if (-not (Test-Path $ProfileDir)) {
    New-Item -ItemType Directory -Path $ProfileDir -Force | Out-Null
}

# Create Profile file if it doesn't exist
if (-not (Test-Path $PROFILE)) {
    New-Item -ItemType File -Path $PROFILE -Force | Out-Null
}

# Code block to append
$CodeBlock = @"

# --- FlatSat Global Shortcuts (Auto-generated) ---
`$FLATSAT_DIR = "$flatsat_dir"

function flatsat {
    `$cli_path = "`$FLATSAT_DIR\flatsat-ground-station\flatsat_cli.py"
    `$python_path = "`$FLATSAT_DIR\flatsat-ground-station\.venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath "`$python_path")) {
        `$python_path = "python"
    }
    if (Test-Path -LiteralPath "`$cli_path") {
        & `$python_path "`$cli_path" `@args
    } else {
        Write-Host "Error: No se encontro flatsat_cli.py en `$cli_path" -ForegroundColor Red
    }
}

function flatsat-tui {
    `$tui_path = "`$FLATSAT_DIR\flat-sat-fw-interno"
    `$python_path = "`$FLATSAT_DIR\flat-sat-fw-interno\.venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath "`$python_path")) {
        `$python_path = "python"
    }
    if (Test-Path -LiteralPath "`$tui_path\flatsatTUI") {
        Set-Location -LiteralPath "`$tui_path"
        & `$python_path -m flatsatTUI `@args
    } else {
        Write-Host "Error: No se encontro flatsatTUI en `$tui_path" -ForegroundColor Red
    }
}

function flatsat-web {
    `$app_path = "`$FLATSAT_DIR\flatsat-ground-station"
    `$python_path = "`$FLATSAT_DIR\flatsat-ground-station\.venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath "`$python_path")) {
        `$python_path = "python"
    }
    if (Test-Path -LiteralPath "`$app_path\webapp") {
        Set-Location -LiteralPath "`$app_path"
        & `$python_path -m webapp.app `@args
    } else {
        Write-Host "Error: No se encontro la carpeta de la webapp en `$app_path" -ForegroundColor Red
    }
}
Write-Host "🚀 Atajos de FlatSat cargados exitosamente (flatsat, flatsat-tui, flatsat-web)" -ForegroundColor Green
# --- End FlatSat Global Shortcuts ---
"@

# Read current profile content to avoid duplicate injection
$CurrentContent = ""
if (Test-Path $PROFILE) {
    $CurrentContent = Get-Content $PROFILE -Raw
}

if ($CurrentContent -like "*FlatSat Global Shortcuts (Auto-generated)*") {
    Write-Host "[*] Profile already contains FlatSat shortcuts. Updating paths..." -ForegroundColor Yellow
    # Remove old block and append new
    $CleanContent = $CurrentContent -replace "(?s)# --- FlatSat Global Shortcuts \(Auto-generated\) ---.*?# --- End FlatSat Global Shortcuts ---", ""
    $CleanContent.Trim() + "`r`n`r`n" + $CodeBlock | Out-File $PROFILE -Encoding utf8
} else {
    Write-Host "[+] Injecting shortcuts into profile..." -ForegroundColor Green
    Add-Content -Path $PROFILE -Value "`r`n$CodeBlock" -Encoding utf8
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "[+] SUCCESS! Windows shortcuts configured successfully." -ForegroundColor Green
Write-Host "Please restart your PowerShell terminal or run:" -ForegroundColor Yellow
Write-Host "  . `$PROFILE" -ForegroundColor White
Write-Host "==========================================" -ForegroundColor Cyan
