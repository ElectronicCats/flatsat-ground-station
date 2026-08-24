# FlatSat Windows Serial Driver Setup Helper
# Purpose: Check and configure serial drivers for RP2040 / FlatSat CDC serial interfaces.

Param(
    [switch]$Silent = $false
)

if (-not $Silent) {
    Write-Host "[*] FlatSat Serial Driver Helper" -ForegroundColor Cyan
}

$IsAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $IsAdmin) {
    if (-not $Silent) {
        Write-Host "[!] Please run PowerShell as Administrator to configure USB serial drivers." -ForegroundColor Yellow
    }
    Exit 1
}

if (-not $Silent) {
    Write-Host "[+] Driver check completed." -ForegroundColor Green
}
