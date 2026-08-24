<#
.SYNOPSIS
    FlatSat Radio Sniffer para Windows 11

.DESCRIPTION
    Captura tramas LoRa/FSK del FlatSat en tiempo real.
    No requiere Python. Usa .NET SerialPort directamente.
    Auto-detecta los puertos COM del FlatSat por VID/PID (1209:BABC).

.PARAMETER Radio
    Radio a escuchar: 0 = downlink telemetria (defecto), 1 = uplink telecomando

.PARAMETER Duration
    Segundos de escucha. 0 = ilimitado hasta Ctrl+C. Defecto: 60

.PARAMETER Output
    Archivo de texto donde guardar las tramas capturadas

.PARAMETER Port
    Puerto COM manual (ej. COM5). Si no se indica, se auto-detecta.

.PARAMETER Count
    Detener despues de N tramas. 0 = sin limite.

.PARAMETER ShowHex
    Mostrar los bytes hex de cada trama recibida

.PARAMETER ListPorts
    Listar puertos FlatSat detectados y salir

.EXAMPLE
    .\flatsat_sniff.ps1
    .\flatsat_sniff.ps1 -Radio 1
    .\flatsat_sniff.ps1 -Duration 0 -Output captura.txt
    .\flatsat_sniff.ps1 -Port COM5 -ShowHex
    .\flatsat_sniff.ps1 -ListPorts
#>

[CmdletBinding()]
param(
    [int]    $Radio    = 0,
    [double] $Duration = 60,
    [string] $Output   = "",
    [string] $Port     = "",
    [int]    $Count    = 0,
    [switch] $ShowHex,
    [switch] $ListPorts
)

Set-StrictMode -Off
$ErrorActionPreference = "Stop"

# ─── Colores ─────────────────────────────────────────────────────────────────

function Write-Green  { param($t) Write-Host $t -ForegroundColor Green  -NoNewline }
function Write-Cyan   { param($t) Write-Host $t -ForegroundColor Cyan   -NoNewline }
function Write-Yellow { param($t) Write-Host $t -ForegroundColor Yellow -NoNewline }
function Write-Red    { param($t) Write-Host $t -ForegroundColor Red    -NoNewline }
function Write-Dim    { param($t) Write-Host $t -ForegroundColor DarkGray -NoNewline }

function Write-Banner {
    Write-Host ""
    Write-Host "  FlatSat Radio Sniffer" -ForegroundColor Cyan
    Write-Host "  ─────────────────────────────────────────" -ForegroundColor DarkGray
}

# ─── Descubrimiento de puertos via WMI ───────────────────────────────────────

function Get-FlatSatPorts {
    <#
    Consulta WMI para encontrar todos los puertos COM del FlatSat (VID=1209, PID=BABC).
    Devuelve un array de objetos con .Port y .InterfaceIndex ordenados por InterfaceIndex.
    InterfaceIndex: 0=Radio0, 2=Radio1, 4=Shell  (mismo mapeo que catnip)
    #>
    $flatsat_ports = @()

    try {
        # Buscar dispositivos USB con nuestro VID y PID en Win32_PnPEntity
        $pnp_devices = Get-WmiObject Win32_PnPEntity -ErrorAction SilentlyContinue |
            Where-Object { $_.HardwareID -match "VID_1209.*PID_BABC" }

        foreach ($dev in $pnp_devices) {
            # Extraer numero de interfaz MI_xx del DeviceID
            $iface_idx = $null
            if ($dev.DeviceID -match "MI_(\d+)") {
                $iface_idx = [int]$Matches[1]
            }

            # Buscar el puerto COM asociado a este dispositivo
            $com_port = $null
            if ($dev.Name -match "(COM\d+)") {
                $com_port = $Matches[1]
            } else {
                # Buscar en Win32_SerialPort por DeviceID
                $serial = Get-WmiObject Win32_SerialPort -ErrorAction SilentlyContinue |
                    Where-Object { $_.PNPDeviceID -like "*VID_1209*PID_BABC*" }
                foreach ($s in $serial) {
                    if ($s.PNPDeviceID -eq $dev.DeviceID) {
                        $com_port = $s.DeviceID
                        break
                    }
                }
            }

            if ($com_port -and $null -ne $iface_idx) {
                $flatsat_ports += [PSCustomObject]@{
                    Port           = $com_port
                    InterfaceIndex = $iface_idx
                    Name           = $dev.Name
                }
            }
        }
    } catch {
        # Fallback: buscar por descripcion en Win32_SerialPort
        try {
            $serial_ports = Get-WmiObject Win32_SerialPort -ErrorAction SilentlyContinue |
                Where-Object { $_.Description -match "FlatSat|CatSniffer|Electronic Cats|CAT-" }
            foreach ($s in $serial_ports) {
                $flatsat_ports += [PSCustomObject]@{
                    Port           = $s.DeviceID
                    InterfaceIndex = $null
                    Name           = $s.Description
                }
            }
        } catch { }
    }

    return ($flatsat_ports | Sort-Object InterfaceIndex)
}

function Resolve-RadioPort {
    param([int]$RadioIdx, [string]$ManualPort)

    # Puerto manual
    if ($ManualPort -ne "") {
        return $ManualPort
    }

    $ports = Get-FlatSatPorts

    if ($ports.Count -eq 0) {
        return $null
    }

    # Mapeo de indice de interfaz a radio
    # 0 = Radio0 (downlink), 2 = Radio1 (uplink), 4 = Shell
    $target_iface = if ($RadioIdx -eq 0) { 0 } else { 2 }

    # Buscar por indice de interfaz exacto
    $match = $ports | Where-Object { $_.InterfaceIndex -eq $target_iface }
    if ($match) {
        return $match.Port
    }

    # Fallback posicional: si hay 3 puertos, tomar el primero o segundo
    if ($ports.Count -ge 2) {
        return $ports[$RadioIdx].Port
    }

    # Ultimo recurso: primer puerto disponible
    return $ports[0].Port
}

function Normalize-COMPort {
    param([string]$PortName)
    # COM10 y superiores necesitan prefijo \\.\  en Win32
    if ($PortName -match "^COM(\d+)$") {
        $num = [int]$Matches[1]
        if ($num -ge 10) {
            return "\\.\$PortName"
        }
    }
    return $PortName
}

# ─── Parser de lineas RX ──────────────────────────────────────────────────────

function Parse-RXLine {
    param([string]$Line)

    # LoRa: "RX: <hex> | RSSI: <int> | SNR: <int>"
    if ($Line -match '^RX:\s*([A-Fa-f0-9]+)\s*\|\s*RSSI:\s*(-?\d+)\s*\|\s*SNR:\s*(-?\d+)') {
        return [PSCustomObject]@{
            Mode = "LoRa"
            Hex  = $Matches[1]
            RSSI = [int]$Matches[2]
            SNR  = [int]$Matches[3]
        }
    }

    # FSK: "FSK RX: <hex> | RSSI: <int> | Len: <int>"
    if ($Line -match '^FSK RX:\s*([A-Fa-f0-9]+)\s*\|\s*RSSI:\s*(-?\d+)\s*\|\s*Len:\s*(\d+)') {
        return [PSCustomObject]@{
            Mode = "FSK"
            Hex  = $Matches[1]
            RSSI = [int]$Matches[2]
            SNR  = $null
        }
    }

    return $null
}

# ─── Formato de salida ────────────────────────────────────────────────────────

function Write-Frame {
    param([int]$Count, $RX, [bool]$ShowHexData)

    $ts     = (Get-Date).ToString("HH:mm:ss.fff")
    $nbytes = $RX.Hex.Length / 2
    $snr_str = if ($null -ne $RX.SNR) { " SNR $($RX.SNR) dB" } else { "" }

    # Color segun RSSI
    $rssi_color = if ($RX.RSSI -ge -70) { "Green" }
                  elseif ($RX.RSSI -ge -90) { "Yellow" }
                  else { "Red" }

    Write-Host "  [" -NoNewline
    Write-Host $ts -ForegroundColor DarkGray -NoNewline
    Write-Host "] #" -NoNewline
    Write-Host $Count -ForegroundColor White -NoNewline
    Write-Host "  " -NoNewline
    Write-Host $RX.Mode -ForegroundColor Cyan -NoNewline
    Write-Host "  RSSI " -NoNewline
    Write-Host "$($RX.RSSI) dBm" -ForegroundColor $rssi_color -NoNewline
    Write-Host "$snr_str" -NoNewline
    Write-Host "  " -NoNewline
    Write-Host "$nbytes bytes" -ForegroundColor DarkGray

    if ($ShowHexData) {
        $hex = $RX.Hex.ToUpper()
        for ($i = 0; $i -lt $hex.Length; $i += 32) {
            $chunk = $hex.Substring($i, [Math]::Min(32, $hex.Length - $i))
            $formatted = ($chunk -split "(..)").Where({$_}) -join " "
            Write-Host "    $formatted" -ForegroundColor DarkGray
        }
        Write-Host ""
    }
}

# ─── Sniff principal ──────────────────────────────────────────────────────────

function Start-Sniff {
    param(
        [string] $TargetPort,
        [double] $SniffDuration,
        [string] $OutFile,
        [bool]   $ShowHexData,
        [int]    $MaxFrames
    )

    $normalized = Normalize-COMPort $TargetPort

    Write-Host "  Puerto  : " -NoNewline -ForegroundColor DarkGray
    Write-Host $TargetPort -ForegroundColor White
    Write-Host "  Tiempo  : " -NoNewline -ForegroundColor DarkGray
    if ($SniffDuration -le 0) {
        Write-Host "ilimitado (Ctrl+C para detener)" -ForegroundColor Yellow
    } else {
        Write-Host "$($SniffDuration)s" -ForegroundColor White
    }
    if ($OutFile -ne "") {
        Write-Host "  Salida  : $OutFile" -ForegroundColor DarkGray
    }
    Write-Host ""

    # Crear el puerto serial .NET
    try {
        $sp = New-Object System.IO.Ports.SerialPort
        $sp.PortName  = $normalized
        $sp.BaudRate  = 115200
        $sp.Parity    = [System.IO.Ports.Parity]::None
        $sp.DataBits  = 8
        $sp.StopBits  = [System.IO.Ports.StopBits]::One
        $sp.Handshake = [System.IO.Ports.Handshake]::None
        $sp.DtrEnable = $true     # CRITICO: Zephyr CDC ACM requiere DTR=True en Windows
        $sp.RtsEnable = $false
        $sp.ReadTimeout  = 1000   # 1 segundo — igual que catnip ShellConnection
        $sp.WriteTimeout = 1000

        $sp.Open()
    } catch {
        Write-Host "  ERROR: No se pudo abrir $TargetPort" -ForegroundColor Red
        Write-Host "  $_" -ForegroundColor DarkRed
        Write-Host ""
        Write-Host "  Sugerencias:" -ForegroundColor Yellow
        Write-Host "   - Verifica que el FlatSat este conectado" -ForegroundColor DarkGray
        Write-Host "   - Usa -ListPorts para ver los puertos disponibles" -ForegroundColor DarkGray
        Write-Host "   - Cierra cualquier otro programa que use el puerto (PuTTY, etc.)" -ForegroundColor DarkGray
        exit 1
    }

    Write-Host "  Escuchando..." -ForegroundColor Green -NoNewline
    Write-Host "  (Ctrl+C para detener)" -ForegroundColor DarkGray
    Write-Host ""

    $frame_count = 0
    $log_lines   = [System.Collections.Generic.List[string]]::new()
    $start_time  = [System.Diagnostics.Stopwatch]::StartNew()

    try {
        while ($true) {
            # Verificar timeout
            if ($SniffDuration -gt 0 -and $start_time.Elapsed.TotalSeconds -ge $SniffDuration) {
                break
            }

            # Leer linea
            try {
                $line = $sp.ReadLine()
            } catch [System.TimeoutException] {
                continue
            } catch {
                Write-Host "  Error de lectura: $_" -ForegroundColor Red
                break
            }

            $line = $line.Trim()
            if ($line -eq "") { continue }

            # Parsear
            $rx = Parse-RXLine $line
            if ($null -eq $rx) { continue }

            $frame_count++
            $ts_iso = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss.fff")

            # Mostrar
            Write-Frame $frame_count $rx $ShowHexData

            # Guardar en log
            if ($OutFile -ne "") {
                $snr_val = if ($null -ne $rx.SNR) { $rx.SNR } else { "N/A" }
                $log_lines.Add("$ts_iso | $($rx.Mode) | RSSI $($rx.RSSI) | SNR $snr_val | $($rx.Hex)")
            }

            # Limite de tramas
            if ($MaxFrames -gt 0 -and $frame_count -ge $MaxFrames) {
                Write-Host ""
                Write-Host "  Limite de $MaxFrames tramas alcanzado." -ForegroundColor Yellow
                break
            }
        }
    } finally {
        try { $sp.Close() } catch { }

        $elapsed = [Math]::Round($start_time.Elapsed.TotalSeconds, 1)
        Write-Host ""
        Write-Host "  ─────────────────────────────────────────" -ForegroundColor DarkGray
        Write-Host "  Tiempo total : $($elapsed)s" -ForegroundColor DarkGray
        Write-Host "  Tramas capturadas : $frame_count" -ForegroundColor White

        if ($OutFile -ne "" -and $log_lines.Count -gt 0) {
            try {
                $header = @(
                    "# FlatSat Sniff — $((Get-Date).ToString('yyyy-MM-ddTHH:mm:ss'))",
                    "# Puerto: $TargetPort",
                    "# Formato: timestamp | mode | RSSI | SNR | hex",
                    ""
                )
                ($header + $log_lines) | Set-Content -Path $OutFile -Encoding UTF8
                Write-Host "  Guardado en  : $OutFile" -ForegroundColor Green
            } catch {
                Write-Host "  Error al guardar: $_" -ForegroundColor Red
            }
        } elseif ($OutFile -ne "") {
            Write-Host "  No se capturo ninguna trama." -ForegroundColor Yellow
        }
        Write-Host ""
    }
}

# ─── Punto de entrada ─────────────────────────────────────────────────────────

Write-Banner

# --list-ports
if ($ListPorts) {
    Write-Host "  Buscando puertos FlatSat..." -ForegroundColor DarkGray
    Write-Host ""
    $ports = Get-FlatSatPorts
    if ($ports.Count -eq 0) {
        Write-Host "  No se encontro ningun FlatSat conectado." -ForegroundColor Yellow
        Write-Host "  Asegurate de que el cable USB este conectado y el driver instalado." -ForegroundColor DarkGray
    } else {
        $role_map = @{0="Radio0 (downlink)"; 2="Radio1 (uplink)"; 4="Shell (config)"}
        foreach ($p in $ports) {
            $role = if ($null -ne $p.InterfaceIndex -and $role_map.ContainsKey($p.InterfaceIndex)) {
                $role_map[$p.InterfaceIndex]
            } else { "Desconocido" }
            Write-Host "  " -NoNewline
            Write-Host "$($p.Port)" -ForegroundColor Cyan -NoNewline
            Write-Host "  ->  $role" -ForegroundColor White -NoNewline
            Write-Host "  [$($p.Name)]" -ForegroundColor DarkGray
        }
    }
    Write-Host ""
    exit 0
}

# Resolver puerto
$resolved_port = Resolve-RadioPort -RadioIdx $Radio -ManualPort $Port
if ($null -eq $resolved_port) {
    Write-Host "  No se encontro el FlatSat conectado." -ForegroundColor Red
    Write-Host "  Usa -ListPorts para ver los puertos disponibles." -ForegroundColor DarkGray
    Write-Host "  Usa -Port COM<N> para especificar el puerto manualmente." -ForegroundColor DarkGray
    Write-Host ""
    exit 1
}

Write-Host "  Radio   : $Radio" -ForegroundColor DarkGray

Start-Sniff `
    -TargetPort  $resolved_port `
    -SniffDuration $Duration `
    -OutFile     $Output `
    -ShowHexData $ShowHex.IsPresent `
    -MaxFrames   $Count
