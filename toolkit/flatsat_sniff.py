#!/usr/bin/env python3
"""
flatsat_sniff.py — FlatSat Radio Sniffer
=========================================
Script standalone para capturar tramas LoRa/FSK del FlatSat en tiempo real.
Compatible con Windows 11, Linux y macOS.

Uso:
    python flatsat_sniff.py                        # Escucha Radio 0, 60 segundos
    python flatsat_sniff.py -r 1                   # Escucha Radio 1 (uplink)
    python flatsat_sniff.py -t 0                   # Hasta Ctrl+C
    python flatsat_sniff.py -t 120 -o capture.txt  # 2 minutos, guarda en archivo
    python flatsat_sniff.py --port COM5            # Puerto manual
    python flatsat_sniff.py --hex                  # Muestra hex completo de cada trama

Requiere: pyserial
    pip install pyserial
"""

import argparse
import re
import sys
import time
from datetime import datetime

# ─── Constantes ──────────────────────────────────────────────────────────────

USB_VID = 0x1209
USB_PID = 0xBABC
BAUDRATE = 115200

# Interfaz USB → rol  (mismo mapeo que catnip: 0=Radio0, 2=Radio1, 4=Shell)
_INTF_TO_ROLE = {0: "radio0", 2: "radio1", 4: "shell"}

# ─── Colores ANSI (desactivados si no hay terminal o en Windows sin soporte) ─

_COLOR = sys.stdout.isatty()

def _c(code, text):
    return f"\033[{code}m{text}\033[0m" if _COLOR else text

def _green(t):  return _c("92", t)
def _cyan(t):   return _c("96", t)
def _yellow(t): return _c("93", t)
def _red(t):    return _c("91", t)
def _dim(t):    return _c("2",  t)
def _bold(t):   return _c("1",  t)


# ─── Descubrimiento de puertos (mismo algoritmo que catnip) ──────────────────

def _is_flatsat(p) -> bool:
    """Comprueba si un puerto pertenece al FlatSat por VID/PID o descripción."""
    try:
        if p.vid == USB_VID and p.pid == USB_PID:
            return True
    except AttributeError:
        pass
    hwid = (getattr(p, "hwid", "") or "").upper()
    if "1209" in hwid and "BABC" in hwid:
        return True
    desc = (getattr(p, "description", "") or "").upper()
    for kw in ("FLATSAT", "CATSNIFFER", "CAT-RADIO", "CAT-SHELL", "ELECTRONIC CATS"):
        if kw in desc:
            return True
    return False


def _normalize(path: str) -> str:
    """Añade \\.\\ a puertos COM10+ en Windows."""
    if sys.platform == "win32" and path:
        u = path.upper()
        if u.startswith("COM") and not u.startswith(r"\\.\COM"):
            try:
                if int(u[3:]) >= 10:
                    return rf"\\.\{u}"
            except ValueError:
                pass
    return path


def _intf_index(port) -> int | None:
    """Extrae el índice de interfaz USB desde HWID o location (igual que catnip)."""
    hwid = (getattr(port, "hwid", "") or "").upper()
    loc  = (getattr(port, "location", "") or "")

    # Windows PySerial: "USB VID:PID=1209:BABC SER=... LOCATION=1-2:x.4"
    m = re.search(r"LOCATION=\S+:(?:\w+)\.(\d+)", hwid, re.IGNORECASE)
    if m:
        return int(m.group(1))

    # Windows Device Manager HWID: "USB\VID_1209&PID_BABC&MI_04\..."
    m = re.search(r"[&\\]MI[=_]?(\d+)", hwid, re.IGNORECASE)
    if m:
        return int(m.group(1))

    # Linux / macOS location: "1-7:1.2"
    if loc and ":" in loc:
        try:
            return int(loc.split(":")[-1].split(".")[-1])
        except (ValueError, IndexError):
            pass

    return None


def _group_key(port) -> str:
    """Clave de agrupación por dispositivo físico (igual que catnip)."""
    hwid = port.hwid or ""
    m = re.search(r"SER[=:]([A-Fa-f0-9]+)", hwid)
    if m:
        return m.group(1)
    if port.serial_number:
        return port.serial_number
    loc = getattr(port, "location", "") or ""
    if ":" in loc:
        return loc.split(":")[0]
    return f"unknown-{port.device}"


def discover_ports() -> dict:
    """
    Devuelve un dict {'radio0': path, 'radio1': path, 'shell': path}
    del primer FlatSat encontrado, o {} si no hay ninguno.
    """
    try:
        import serial.tools.list_ports
    except ImportError:
        return {}

    all_ports = list(serial.tools.list_ports.comports())
    cat_ports = [p for p in all_ports if _is_flatsat(p)]
    if not cat_ports:
        return {}

    # Agrupar por dispositivo físico
    groups: dict[str, list] = {}
    for p in cat_ports:
        key = _group_key(p)
        groups.setdefault(key, []).append(p)

    # Tomar el primer grupo con ≥2 puertos
    for key, ports in groups.items():
        ports.sort(key=lambda p: p.device)
        result: dict[str, str] = {}

        # Estrategia 1: descripción
        for p in ports:
            desc = (p.description or "").lower()
            if "shell" in desc and "shell" not in result:
                result["shell"] = p.device
            elif ("radio0" in desc or "radio 0" in desc) and "radio0" not in result:
                result["radio0"] = p.device
            elif ("radio1" in desc or "radio 1" in desc) and "radio1" not in result:
                result["radio1"] = p.device

        # Estrategia 2: índice de interfaz USB
        if len(result) < 3:
            for p in ports:
                idx = _intf_index(p)
                if idx is not None:
                    role = _INTF_TO_ROLE.get(idx)
                    if role and role not in result:
                        result[role] = p.device

        # Estrategia 3: posición (Radio0, Radio1, Shell en orden ascendente)
        if len(result) < 2:
            roles = ["radio0", "radio1", "shell"]
            used = set(result.values())
            ri = 0
            for p in sorted(ports, key=lambda x: x.device):
                if p.device in used:
                    continue
                while ri < len(roles) and roles[ri] in result:
                    ri += 1
                if ri >= len(roles):
                    break
                result[roles[ri]] = p.device
                used.add(p.device)
                ri += 1

        if result.get("radio0") or result.get("radio1"):
            # Normalizar COM10+
            return {k: _normalize(v) for k, v in result.items()}

    return {}


# ─── Parser de líneas RX ─────────────────────────────────────────────────────

def parse_rx(line: str) -> dict | None:
    """
    Parsea líneas del formato:
        LoRa: "RX: <hex> | RSSI: <int> | SNR: <int>"
        FSK:  "FSK RX: <hex> | RSSI: <int> | Len: <int>"
    Devuelve dict o None.
    """
    m = re.match(
        r"RX:\s*([A-Fa-f0-9]+)\s*\|\s*RSSI:\s*(-?\d+)\s*\|\s*SNR:\s*(-?\d+)",
        line,
    )
    if m:
        return {"mode": "LoRa", "hex": m.group(1),
                "rssi": int(m.group(2)), "snr": int(m.group(3))}

    m = re.match(
        r"FSK RX:\s*([A-Fa-f0-9]+)\s*\|\s*RSSI:\s*(-?\d+)\s*\|\s*Len:\s*(\d+)",
        line,
    )
    if m:
        return {"mode": "FSK ", "hex": m.group(1),
                "rssi": int(m.group(2)), "snr": None}

    return None


# ─── Formateo de tramas ───────────────────────────────────────────────────────

def format_frame(count: int, rx: dict, show_hex: bool) -> list[str]:
    """Genera las líneas de salida para un frame recibido."""
    ts   = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    mode = rx["mode"]
    rssi = rx["rssi"]
    snr  = rx.get("snr")
    raw  = rx["hex"]
    nbytes = len(raw) // 2

    snr_str  = f" SNR {snr:+d} dB" if snr is not None else ""
    hdr = (
        f"[{_dim(ts)}] "
        f"#{_bold(str(count))} "
        f"{_cyan(mode)} "
        f"RSSI {_rssi_color(rssi)}{rssi} dBm{snr_str}"
        f"  {_dim(f'{nbytes} bytes')}"
    )

    lines = [hdr]
    if show_hex:
        # Imprimir hex en grupos de 16 bytes
        for i in range(0, len(raw), 32):
            chunk = raw[i:i+32]
        lines.append(_dim("    " + " ".join(chunk[j:j+2] for j in range(0, len(chunk), 2))))

    return lines


def _rssi_color(rssi: int):
    """Color según potencia de señal."""
    if rssi >= -70:
        return "\033[92m" if _COLOR else ""   # verde fuerte
    elif rssi >= -90:
        return "\033[93m" if _COLOR else ""   # amarillo
    else:
        return "\033[91m" if _COLOR else ""   # rojo


# ─── Loop principal de sniffing ───────────────────────────────────────────────

def sniff(port: str, duration: float, output_path: str | None,
          show_hex: bool, max_frames: int) -> None:
    """Loop de escucha serial. Ctrl+C para detener."""
    import serial

    print(_bold(f"\n  FlatSat Radio Sniffer"))
    print(_dim(f"  Puerto : {port}"))
    print(_dim(f"  Tiempo : {'ilimitado (Ctrl+C)' if duration <= 0 else f'{duration}s'}"))
    if output_path:
        print(_dim(f"  Salida : {output_path}"))
    print()

    lines_captured = []
    frame_count = 0
    start = time.monotonic()

    try:
        # Abre el puerto con DTR=True (requerido por Zephyr CDC ACM en Windows)
        ser = serial.Serial(
            port,
            BAUDRATE,
            timeout=1.0,        # blocking read — mismo que catnip ShellConnection
            dsrdtr=False,
            rtscts=False,
        )
        ser.dtr = True          # señaliza "host conectado" al firmware Zephyr

        print(_green("  Escuchando... ") + _dim("(Ctrl+C para detener)\n"))

        while True:
            # Verificar timeout
            if duration > 0 and time.monotonic() - start >= duration:
                break

            try:
                raw_line = ser.readline()
            except serial.SerialException as e:
                print(_red(f"  Error serial: {e}"))
                break

            if not raw_line:
                continue

            line = raw_line.decode("ascii", errors="ignore").strip()
            if not line:
                continue

            rx = parse_rx(line)
            if not rx:
                continue

            frame_count += 1
            ts_iso = datetime.now().isoformat()

            for text_line in format_frame(frame_count, rx, show_hex):
                print(text_line)
            if show_hex:
                print()

            # Guardar en log
            if output_path:
                lines_captured.append(
                    f"{ts_iso} | {rx['mode'].strip()} | "
                    f"RSSI {rx['rssi']} | SNR {rx.get('snr', 'N/A')} | "
                    f"{rx['hex']}\n"
                )

            if max_frames and frame_count >= max_frames:
                print(_yellow(f"\n  Límite de {max_frames} tramas alcanzado."))
                break

    except serial.SerialException as e:
        print(_red(f"  No se pudo abrir el puerto {port}: {e}"))
        sys.exit(1)
    except KeyboardInterrupt:
        print(_yellow("\n\n  Sniffing detenido por el usuario."))
    finally:
        try:
            ser.close()
        except Exception:
            pass

    elapsed = time.monotonic() - start
    print(_dim(f"\n  Tiempo total : {elapsed:.1f}s"))
    print(_dim(f"  Tramas       : {frame_count}"))

    if output_path and lines_captured:
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(f"# FlatSat Sniff — {datetime.now().isoformat()}\n")
                f.write(f"# Puerto: {port}\n")
                f.write(f"# Formato: timestamp | mode | RSSI | SNR | hex\n\n")
                f.writelines(lines_captured)
            print(_green(f"  Guardado     : {output_path}"))
        except OSError as e:
            print(_red(f"  Error al guardar: {e}"))
    elif output_path:
        print(_yellow("  No se capturó ninguna trama."))

    print()


# ─── Entrada principal ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="FlatSat Radio Sniffer — captura tramas LoRa/FSK en tiempo real.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python flatsat_sniff.py                         # Radio 0, 60 segundos
  python flatsat_sniff.py -r 1                    # Radio 1 (uplink)
  python flatsat_sniff.py -t 0                    # Hasta Ctrl+C
  python flatsat_sniff.py -t 120 -o capture.txt   # 2 minutos, guarda log
  python flatsat_sniff.py --port COM5             # Puerto manual en Windows
  python flatsat_sniff.py --hex                   # Muestra bytes hex
        """,
    )
    parser.add_argument(
        "-r", "--radio", type=int, choices=[0, 1], default=0,
        help="Radio a escuchar: 0=downlink (defecto), 1=uplink"
    )
    parser.add_argument(
        "-t", "--duration", type=float, default=60.0,
        help="Segundos de escucha (0 = ilimitado hasta Ctrl+C). Defecto: 60"
    )
    parser.add_argument(
        "-o", "--output", type=str, default=None,
        help="Archivo de salida para guardar las tramas capturadas"
    )
    parser.add_argument(
        "-n", "--count", type=int, default=0,
        help="Detener después de N tramas (0 = sin límite)"
    )
    parser.add_argument(
        "--port", type=str, default=None,
        help="Puerto COM/ttyACM manual (si no se especifica, se auto-detecta)"
    )
    parser.add_argument(
        "--hex", action="store_true",
        help="Mostrar los bytes hex de cada trama recibida"
    )
    parser.add_argument(
        "--list-ports", action="store_true",
        help="Listar puertos FlatSat detectados y salir"
    )

    args = parser.parse_args()

    # ── Verificar pyserial ────────────────────────────────────────────────────
    try:
        import serial  # noqa: F401
    except ImportError:
        print(_red("Error: pyserial no está instalado."))
        print("  Instalar con:  pip install pyserial")
        sys.exit(1)

    # ── --list-ports ──────────────────────────────────────────────────────────
    if args.list_ports:
        ports = discover_ports()
        if not ports:
            print(_yellow("No se encontró ningún FlatSat conectado."))
        else:
            print(_bold("Puertos FlatSat detectados:"))
            for role, path in ports.items():
                print(f"  {_cyan(role):<14} {path}")
        sys.exit(0)

    # ── Resolver puerto ───────────────────────────────────────────────────────
    if args.port:
        target_port = _normalize(args.port)
    else:
        ports = discover_ports()
        role_key = f"radio{args.radio}"
        if ports.get(role_key):
            target_port = ports[role_key]
        elif not ports:
            print(_red("No se encontró ningún FlatSat conectado."))
            print(_dim("  Usa --port <COMx> para especificar el puerto manualmente."))
            print(_dim("  Usa --list-ports para ver los puertos disponibles."))
            sys.exit(1)
        else:
            # Si no encontró el radio pedido, toma el primero disponible
            target_port = next(iter(ports.values()))
            print(_yellow(f"  Radio {args.radio} no detectado, usando: {target_port}"))

    # ── Sniff ─────────────────────────────────────────────────────────────────
    sniff(
        port=target_port,
        duration=args.duration,
        output_path=args.output,
        show_hex=args.hex,
        max_frames=args.count,
    )


if __name__ == "__main__":
    main()
