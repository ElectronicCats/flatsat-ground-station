#!/usr/bin/env python3
"""FlatSat Host Command Line Interface (CLI) Tool.

Provides a clean interface to discover, check status, configure, and control
FlatSat boards directly from the command line without opening minicom.
"""

import argparse
import sys
import time
import serial

from rich.console import Console
from rich.table import Table
from rich import box

from core.serial_manager import discover_devices
from core.device import FlatSatDevice

console = Console()


def flatsat_get_devices():
    """Return all connected FlatSat boards with their ACM port mapping.

    Mirrors catnip_get_devices() from CatSniffer: a thin, importable wrapper
    around the discovery routine so callers don't need to know it lives in
    core.serial_manager.
    """
    return discover_devices()


def get_selected_device(serial_number=None, port=None):
    """Resolve which device to connect to."""
    devices = flatsat_get_devices()
    
    if not devices:
        if port:
            # Fallback to direct port if provided, mock a DiscoveredDevice structure
            from core.serial_manager import DiscoveredDevice, DeviceIdentity, ENDPOINT_SHELL, ENDPOINT_RADIO0
            print(f"[*] No devices auto-discovered. Attempting direct shell connection on: {port}")
            identity = DeviceIdentity(serial_number="direct")
            ports = {ENDPOINT_SHELL: port, ENDPOINT_RADIO0: port} # Minimal endpoints mapping
            return FlatSatDevice(DiscoveredDevice(identity=identity, ports=ports))
        print("[-] Error: No FlatSat boards detected. Is it plugged in?")
        sys.exit(1)
        
    if len(devices) == 1:
        device = devices[0]
        if serial_number and device.serial_number != serial_number:
            print(f"[-] Error: Requested device {serial_number} not found. Found: {device.serial_number}")
            sys.exit(1)
        return FlatSatDevice(device)
        
    if serial_number:
        for d in devices:
            if d.identity.serial_number == serial_number:
                return FlatSatDevice(d)
        print(f"[-] Error: Device with serial number {serial_number} not found.")
        print("[*] Available devices:")
        for d in devices:
            print(f"  - {d.identity.serial_number} (Shell: {d.shell_port})")
        sys.exit(1)
        
    # Multiple devices, none specified
    print("[!] Multiple FlatSat devices connected. Please specify one with --serial:")
    for d in devices:
        print(f"  - Serial: {d.identity.serial_number} | Shell: {d.shell_port} | Health: {d.health.name}")
    sys.exit(1)


def print_banner():
    banner = """\033[1;35m╭─ Electronic Cats - PWNLAB ───────────────────────────────────────────────────╮
│                                                                              │
│        :=--             --=-       |                                         │
│        -====-         -=====       |                                         │
│        :===================-       |                                         │
│         ===================:       |                                         │
│    -   :==--===========--==-   -   |  flatsat                                │
│   -===:===-   :=====-   -==-.-=--  |  v1.0.0                                 │
│  --    ====-   :===-   -====    -- |  Your FlatSat control terminal.         │
│  -=:   :===================-   .=- |                                         │
│   ---=-- -===============-  -=---  |                                         │
│   ---       --=======--        --  |                                         │
│                                                                              │
╰──────────────────────────────────────────────────────────────────────────────╯\033[0m"""
    print(banner)


def print_title(text):
    print(f"\033[1;36m=== {text} ===\033[0m")


_HEALTH_STYLE = {
    "HEALTHY": "green",
    "PARTIAL": "yellow",
    "CRITICAL": "red",
}


def print_devices_table(devices):
    """Render connected FlatSat boards as a rich table (catnip-style)."""
    table = Table(title=f"Found {len(devices)} FlatSat device(s)", box=box.ROUNDED)
    table.add_column("Device", style="magenta bold", justify="left", no_wrap=True)
    table.add_column("Radio 0 (CDC0)", style="cyan", justify="left")
    table.add_column("Radio 1 (CDC1)", style="cyan", justify="left")
    table.add_column("Shell (CDC2)", style="cyan", justify="left")
    table.add_column("Health", justify="left")

    for i, d in enumerate(devices):
        radio0 = d.radio0_port or "[red]Not found[/red]"
        radio1 = d.radio1_port or "[red]Not found[/red]"
        shell = d.shell_port or "[red]Not found[/red]"
        health_style = _HEALTH_STYLE.get(d.health.name, "white")
        health = f"[{health_style}]{d.health.name}[/{health_style}]"

        table.add_row(
            f"[{i}] {d.identity.serial_number}", radio0, radio1, shell, health
        )

    console.print()
    console.print(table)


def print_help_menu():
    help_text = """\033[1;33m=== COMANDOS DISPONIBLES ===\033[0m
  \033[1mflatsat devices\033[0m     - Muestra las placas FlatSat conectadas y sus puertos.
  \033[1mflatsat status\033[0m      - Verifica si el satélite responde y qué radios están activas.
  \033[1mflatsat sensors\033[0m     - Muestra las lecturas de los sensores (temperatura, aceleración, etc.).
  \033[1mflatsat mode [gs|sat]\033[0m- Cambia entre modo SAT (satélite automático) y GS (estación de tierra).
  \033[1mflatsat flight [state]\033[0m- Cambia o lee el estado de vuelo (safe, nominal, idle, debug).
  \033[1mflatsat difficulty [N]\033[0m- Configura o lee el nivel del taller (Nivel 1, 2 o 3).
  \033[1mflatsat color [R G B]\033[0m - Cambia el color del LED Neopixel en la placa (valores 0-255).
  \033[1mflatsat identify\033[0m    - Hace parpadear los LEDs físicos de la placa para ubicarla.
  \033[1mflatsat reboot\033[0m      - Reinicia la placa y la manda a modo de carga de firmware (BOOTSEL).
  \033[1mflatsat cmd "[comando]"\033[0m- Envía un comando de texto crudo directamente a la terminal de la placa.
  \033[1mflatsat config\033[0m      - Configura y aplica parámetros LoRa de las radios.
      \033[3mParámetros de config:\033[0m
      --radio [0|1]     (Selecciona la radio a configurar)
      --freq [Hz]       (Frecuencia, ej: 915000000)
      --sf [7-12]       (Spreading Factor)
      --bw [125|250|500](Bandwidth en kHz)
      --cr [5-8]        (Coding Rate)
      --power [dBm]     (Potencia de transmisión)
      --syncword [val]  (Palabra de sincronía, ej: 0x2D)
      --mode [stream|command] (Modo de la radio)
      --apply           (Aplica los cambios staged al hardware inmediatamente)
"""
    print(help_text)


def send_cmd(dev, cmd):
    resp = dev.send_shell_command_full(cmd)
    if resp:
        resp = resp.strip()
        cmd_stripped = cmd.strip()
        if resp.startswith(cmd_stripped):
            resp = resp[len(cmd_stripped):].strip()
        return resp
    return None


def main():
    parser = argparse.ArgumentParser(
        description="FlatSat Host CLI - Manage and configure your FlatSat boards easily.",
        add_help=False,
    )
    parser.add_argument("-h", "--help", action="store_true", help="Show this help menu and exit.")
    parser.add_argument("-s", "--serial", help="Serial number of the target FlatSat board.")
    parser.add_argument("-p", "--port", help="Force direct connection to a custom shell port (e.g. /dev/ttyACM3).")
    
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")
    
    # 1. devices
    subparsers.add_parser("devices", help="List all connected FlatSat boards and their endpoints.")
    
    # 2. status
    subparsers.add_parser("status", help="Read system status and firmware information.")
    
    # 3. sensors
    subparsers.add_parser("sensors", help="Read live telemetry data from BME280 and LIS2DH sensors.")
    
    # 4. mode
    mode_parser = subparsers.add_parser("mode", help="Get or set satellite operation mode.")
    mode_parser.add_argument("value", nargs="?", choices=["gs", "sat", "tinygs"], help="Target mode")
    
    # 5. flight
    flight_parser = subparsers.add_parser("flight", help="Get or set flight operational state.")
    flight_parser.add_argument("value", nargs="?", choices=["safe", "nominal", "idle", "debug"], help="Operational state")
    
    # 6. difficulty
    diff_parser = subparsers.add_parser("difficulty", help="Get or set workshop security/difficulty level.")
    diff_parser.add_argument("value", nargs="?", type=int, choices=[1, 2, 3], help="Difficulty level")
    
    # 7. color
    color_parser = subparsers.add_parser("color", help="Set custom RGB color on the NeoPixel LED.")
    color_parser.add_argument("r", type=int, help="Red channel (0-255)")
    color_parser.add_argument("g", type=int, help="Green channel (0-255)")
    color_parser.add_argument("b", type=int, help="Blue channel (0-255)")
    
    # 8. config (Radio configuration staging and apply)
    config_parser = subparsers.add_parser("config", help="Stage and apply radio configuration settings.")
    config_parser.add_argument("--radio", type=int, choices=[0, 1], default=0, help="Radio index to configure (0 or 1)")
    config_parser.add_argument("--freq", type=int, help="LoRa frequency in Hz (e.g. 915000000)")
    config_parser.add_argument("--sf", type=int, choices=range(7, 13), help="Spreading Factor (7-12)")
    config_parser.add_argument("--bw", type=int, choices=[125, 250, 500], help="Bandwidth in kHz")
    config_parser.add_argument("--cr", type=int, choices=[5, 6, 7, 8], help="Coding Rate (5-8)")
    config_parser.add_argument("--power", type=int, help="TX power in dBm")
    config_parser.add_argument("--syncword", help="Syncword (public, private, or hex value e.g. 0x2D)")
    config_parser.add_argument("--mode", choices=["stream", "command"], help="LoRa output mode (stream or command)")
    config_parser.add_argument("--apply", action="store_true", help="Apply staged changes immediately")
    
    # 9. identify
    subparsers.add_parser("identify", help="Trigger board LED identification blink.")
    
    # 10. reboot
    subparsers.add_parser("reboot", help="Reboot the board (forces it into BOOTSEL mode).")
    
    # 11. cmd
    cmd_parser = subparsers.add_parser("cmd", help="Send a raw shell command to the FlatSat console.")
    cmd_parser.add_argument("raw", help="The raw command string to execute")

    args = parser.parse_args()

    if args.help or not args.command:
        print_help_menu()
        return

    if args.command == "devices":
        # Execute devices listing
        print_banner()
        devices = flatsat_get_devices()
        if not devices:
            print_title("CONNECTED FLATSAT DEVICES")
            print("  No FlatSat devices detected.")
        else:
            print_devices_table(devices)
        print()
        return

    # For all other commands, resolve device and connect
    dev = get_selected_device(serial_number=args.serial, port=args.port)
    
    # Connect
    connection_res = dev.connect()
    if not connection_res.get("shell"):
        print("[-] Error: Failed to open Shell serial interface.")
        sys.exit(1)
        
    try:
        if args.command == "status":
            print_title("SYSTEM STATUS")
            fw_version = send_cmd(dev, "fw_version")
            status = send_cmd(dev, "status")
            if fw_version:
                print(fw_version.strip())
            if status:
                print(status.strip())
                
        elif args.command == "sensors":
            print_title("TELEMETRY SENSORS")
            output = send_cmd(dev, "sensors")
            if output:
                print(output.strip())
            else:
                print("[-] Failed to retrieve sensor values.")
                
        elif args.command == "mode":
            if args.value:
                output = send_cmd(dev, f"mode {args.value}")
                print(f"[*] {output.strip()}")
            else:
                output = send_cmd(dev, "status")
                # Parse active mode from status response
                print(f"[*] Current status info: {output.strip()}")
                
        elif args.command == "flight":
            if args.value:
                output = send_cmd(dev, f"flight {args.value}")
                print(f"[*] {output.strip()}")
            else:
                output = send_cmd(dev, "flight")
                print(f"[*] Flight State: {output.strip()}")
                
        elif args.command == "difficulty":
            if args.value is not None:
                output = send_cmd(dev, f"difficulty {args.value}")
                print(f"[*] {output.strip()}")
            else:
                output = send_cmd(dev, "difficulty")
                print(f"[*] Security Level: {output.strip()}")
                
        elif args.command == "color":
            output = send_cmd(dev, f"color {args.r} {args.g} {args.b}")
            print(f"[*] {output.strip()}")
            
        elif args.command == "identify":
            print("[*] Identifying FlatSat board (blinking LEDs)...")
            output = send_cmd(dev, "identify")
            if output:
                print(f"[*] {output.strip()}")
                
        elif args.command == "reboot":
            print("[*] Rebooting device into BOOTSEL bootloader mode...")
            dev.send_shell_command("reboot")
            print("[+] Command sent. Device should disconnect shortly.")
            
        elif args.command == "cmd":
            output = send_cmd(dev, args.raw)
            if output:
                print(output.strip())
                
        elif args.command == "config":
            print_title(f"RADIO CONFIGURATION - RADIO {args.radio}")
            
            # Select target radio
            select_res = send_cmd(dev, f"radio{args.radio}")
            print(f"[*] Selecting Radio {args.radio}: {select_res.strip()}")
            
            staged = False
            if args.freq is not None:
                res = send_cmd(dev, f"lora_freq {args.freq}")
                print(f"  - Frequency -> {args.freq} Hz: {res.strip()}")
                staged = True
            if args.sf is not None:
                res = send_cmd(dev, f"lora_sf {args.sf}")
                print(f"  - Spreading Factor -> SF{args.sf}: {res.strip()}")
                staged = True
            if args.bw is not None:
                res = send_cmd(dev, f"lora_bw {args.bw}")
                print(f"  - Bandwidth -> {args.bw} kHz: {res.strip()}")
                staged = True
            if args.cr is not None:
                res = send_cmd(dev, f"lora_cr {args.cr}")
                print(f"  - Coding Rate -> 4/{args.cr}: {res.strip()}")
                staged = True
            if args.power is not None:
                res = send_cmd(dev, f"lora_power {args.power}")
                print(f"  - Power -> {args.power} dBm: {res.strip()}")
                staged = True
            if args.syncword is not None:
                res = send_cmd(dev, f"lora_syncword {args.syncword}")
                print(f"  - Syncword -> {args.syncword}: {res.strip()}")
                staged = True
            if args.mode is not None:
                res = send_cmd(dev, f"lora_mode R{args.radio} {args.mode}")
                print(f"  - Mode -> {args.mode}: {res.strip()}")
                staged = True
                
            if args.apply or staged:
                if args.apply:
                    apply_res = send_cmd(dev, "lora_apply")
                    print(f"[+] Applying changes: {apply_res.strip()}")
                else:
                    print("[!] Note: Changes are STAGED but not yet applied. Run with --apply to write to hardware.")
            else:
                # No staging parameters, show current config
                cfg_res = send_cmd(dev, "lora_config")
                if cfg_res:
                    print(cfg_res.strip())
                    
    finally:
        dev.disconnect()


if __name__ == "__main__":
    main()
