#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Conecta un FlatSat / CatSniffer al Docker Desktop de Windows.

.DESCRIPTION
    Docker Desktop corre los contenedores dentro de una VM WSL2, asi que los
    puertos COM de Windows no existen dentro del contenedor. Docker Desktop
    publica un servidor USB/IP en 'host.docker.internal' y hay que:

      1. Marcar el dispositivo como compartido con usbipd-win (usbipd bind).
         Sin este paso el servidor USB/IP de Docker no lo exporta.
      2. Adjuntarlo por USB/IP desde un contenedor privilegiado con
         --pid=host, usando las herramientas usbip del namespace de PID 1.
         Este contenedor debe SEGUIR EN EJECUCION: si se para, el dispositivo
         se desconecta.
      3. Los nodos /dev/ttyACM* aparecen en la VM y el servicio ground-station
         los recibe via la seccion 'devices:' de docker-compose.yml.

    Ejecuta este script cada vez que reconectes la placa, reinicies Docker
    Desktop o cierres WSL.

.PARAMETER Busid
    BUSID del dispositivo USB. Si se omite, se busca el primer dispositivo con
    VID:PID 1209:BABC (FlatSat) o 1A86:7523 / 0403:6001 (adaptadores USB-Serial).

.PARAMETER Detach
    Desconecta el dispositivo y detiene el contenedor que mantiene el attach.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\docker_usb_windows.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\docker_usb_windows.ps1 -Busid 1-4
#>

[CmdletBinding()]
param(
    [string]$Busid,
    [switch]$Detach
)

$ErrorActionPreference = 'Stop'

# Docker escribe el progreso de 'build/compose' por stderr. PowerShell 5.1
# convierte eso en ErrorRecord y con 'Stop' aborta el script aunque el comando
# haya funcionado, asi que a partir de aqui se usan 'Continue' + comprobaciones
# explicitas ($LASTEXITCODE / throw).
$ErrorActionPreference = 'Continue'

# El script se autolocaliza en la raiz del repositorio: asi funciona igual
# lanzalo con doble clic, desde PowerShell o elevado (que arranca en C:\Windows).
$RepoRoot = Split-Path -Parent $PSScriptRoot
if (Test-Path (Join-Path $RepoRoot 'docker-compose.yml')) {
    Set-Location $RepoRoot
}

# Log de la ejecucion (util cuando el script se lanza elevado, donde la salida
# de consola no se puede redirigir desde fuera).
$LogDir = Join-Path $env:TEMP 'flatsat-usbip'
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
$LogFile = Join-Path $LogDir ('docker_usb_windows-{0}.log' -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
Start-Transcript -Path $LogFile | Out-Null
trap { Write-Host "ERROR: $_" -ForegroundColor Red; Stop-Transcript | Out-Null; exit 1 }

$UsbipdCandidates = @(
    "$env:ProgramFiles\usbipd-win\usbipd.exe",
    "$env:LOCALAPPDATA\Microsoft\WinGet\Links\usbipd.exe"
)
$AttachContainer = 'usbip-attach'

function Get-Usbipd {
    $cmd = Get-Command usbipd -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($c in $UsbipdCandidates) {
        if (Test-Path $c) { return $c }
    }
    throw "usbipd-win no encontrado. Instalalo con: winget install usbipd"
}

function Find-FlatSatBusid {
    $lines = & $script:UsbipdExe list 2>&1
    $connected = $false
    foreach ($line in $lines) {
        if ($line -match '^\s*Connected:') { $connected = $true; continue }
        if ($line -match '^\s*Persisted:') { break }
        if (-not $connected) { continue }
        # Filtra los VID:PID de FlatSat (1209:BABC) y adaptadores CDC/USB-Serial comunes
        if ($line -match '^\s*(\S+)\s+((1209:babc)|(1a86:7523)|(0403:6001)|(10c4:ea60))') {
            return $Matches[1]
        }
    }
    return $null
}

$script:UsbipdExe = Get-Usbipd
Write-Host "usbipd: $script:UsbipdExe" -ForegroundColor DarkGray

# ── Modo detach ──────────────────────────────────────────────────────────────
if ($Detach) {
    Write-Host "Desconectando dispositivo de WSL..." -ForegroundColor Yellow
    if (-not $Busid) { $Busid = Find-FlatSatBusid }
    if ($Busid) { & $script:UsbipdExe detach --busid $Busid | Out-Null }

    docker rm -f $AttachContainer 2>&1 | Out-Null
    Write-Host "Contenedor '$AttachContainer' detenido." -ForegroundColor Green
    Stop-Transcript | Out-Null
    return
}

# ── Validar Docker ───────────────────────────────────────────────────────────
if (-not (docker info 2>&1 | Select-String -Pattern 'Server Version')) {
    throw "Docker Desktop no esta corriendo. Inicialo antes de ejecutar este script."
}

# ── Localizar el dispositivo ─────────────────────────────────────────────────
if (-not $Busid) {
    $Busid = Find-FlatSatBusid
    if (-not $Busid) {
        throw @"
No se encontro ningun dispositivo FlatSat/CatSniffer por USB.

  - Comprueba que la placa esta conectada y que Windows la reconoce
    (Administrador de dispositivos > Puertos (COM y LPT)).
  - Si la placa aparece como COM pero no en 'usbipd list', prueba a
    desconectarla y volver a conectarla.
"@
    }
}

Write-Host "Dispositivo FlatSat en BUSID: $Busid" -ForegroundColor Cyan

# ── Paso 1: marcar como compartido (imprescindible para que Docker lo exporte) ──
& $script:UsbipdExe bind --busid $Busid | Out-Null

# ── Paso 2: adjuntar por USB/IP desde un contenedor privilegiado ─────────────
# El attach es idempotente: si el dispositivo ya esta dentro de la VM se
# reutiliza tal cual. Si quedo un attach fantasma (dispositivo exportado pero
# sin nodos en /dev) se suelta primero con 'usbip detach'.

function Test-DeviceInVm {
    # Cuenta los nodos ttyACM/ttyUSB visibles en el namespace de PID 1 de la VM.
    $out = docker run --rm --privileged --pid=host alpine `
        sh -c 'nsenter -t 1 -m -- ls /dev/ttyACM* /dev/ttyUSB* 2>/dev/null | wc -l' 2>&1
    $count = 0
    [int]::tryParse(($out | Select-Object -Last 1).Trim(), [ref]$count) | Out-Null
    return ($count -ge 2)
}

function Test-AttachContainerRunning {
    # 'docker inspect' escribe un error en stderr si el contenedor no existe,
    # asi que primero se comprueba la existencia para no ensuciar la salida.
    $exists = docker ps -a --filter "name=^/$AttachContainer$" --format '{{.Names}}' 2>$null
    if (-not $exists) { return $false }
    $state = docker inspect -f '{{.State.Running}}' $AttachContainer 2>$null
    return ($state -eq 'true')
}

# El cliente USB/IP es el contenedor '$AttachContainer': mientras viva, el
# dispositivo esta conectado de verdad. Si el contenedor no esta corriendo pero
# los nodos siguen en /dev, la adjuncion esta COLGADA (el dispositivo ya no
# responde y abrir el puerto se queda bloqueado para siempre), asi que hay que
# soltarla con 'usbip detach' y volver a adjuntarla.
$attachRunning = Test-AttachContainerRunning
$devicesPresent = Test-DeviceInVm

if ($attachRunning -and $devicesPresent) {
    Write-Host "Dispositivo ya adjunto y activo. Se reutiliza." -ForegroundColor Green
} else {
    if ($devicesPresent -and -not $attachRunning) {
        Write-Host "Se detecta una adjuncion colgada; se va a rehacer." -ForegroundColor Yellow
    }

    # Suelta cualquier attach previo (incluido el colgante).
    docker run --rm --privileged --pid=host alpine `
        sh -c "nsenter -t 1 -m -- usbip detach -r host.docker.internal -d $Busid" 2>&1 | Out-Null

    docker rm -f $AttachContainer 2>&1 | Out-Null

    $containerId = docker run -d --name $AttachContainer --privileged --pid=host alpine `
        sh -c "nsenter -t 1 -m -- usbip attach -r host.docker.internal -d $Busid && echo ATTACHED_OK && sleep infinity" 2>&1

    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo iniciar el contenedor de attach USB/IP: $containerId"
    }

    # El attach tarda unos segundos: espera a la senal de exito.
    $attached = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        if ((docker logs $AttachContainer 2>&1) -match 'ATTACHED_OK') { $attached = $true; break }
        $state = docker inspect -f '{{.State.Status}}' $AttachContainer 2>&1
        if ($state -match 'exited') { break }
    }

    if (-not $attached) {
        Write-Host "El attach USB/IP no completo. Logs del contenedor:" -ForegroundColor Red
        docker logs $AttachContainer 2>&1 | Write-Host
        throw "Attach USB/IP fallido para el BUSID $Busid."
    }

    Write-Host "Dispositivo adjuntado por USB/IP." -ForegroundColor Green
}

# ── Paso 3: reiniciar el servicio para que tome los puertos ──────────────────
Write-Host "Arrancando el servicio ground-station..." -ForegroundColor Cyan
# 'down --remove-orphans' limpio contenedores a medias de despliegues previos,
# que en Docker Desktop dejan el nombre ocupado y bloquean el 'up'.
docker compose down --remove-orphans 2>&1 | Out-Null
docker compose up -d --build 2>&1 | Select-Object -Last 3

# Comprobacion final desde dentro del contenedor
Start-Sleep -Seconds 8
Write-Host ""
Write-Host "Escaneo de dispositivos desde el contenedor:" -ForegroundColor Cyan
docker exec flatsat-ground-station python -c @"
from modules.core.serial_manager import discover_devices
found = discover_devices()
if not found:
    print('  (sin dispositivos)')
for d in found:
    print(f\"  SN:{d.identity.serial_number} r0:{d.radio0_port} r1:{d.radio1_port} shell:{d.shell_port} [{d.health.name}]\")
"@ 2>&1 | Write-Host

Write-Host ""
Write-Host "Webapp: http://localhost:5000" -ForegroundColor Green
Write-Host "Para desconectar:  .\scripts\docker_usb_windows.ps1 -Detach" -ForegroundColor DarkGray
Stop-Transcript | Out-Null
