#!/usr/bin/env python3
"""PR-05: CCSDS frame fuzzer — mutate fields to find parser bugs.

Generates mutated TC frames by corrupting specific CCSDS fields
(APID, opcode, length, sequence counter, payload) to trigger
firmware vulnerabilities like buffer overflows, format strings,
and unexpected state transitions.

Can run offline (print frames) or online (send via serial).
"""

import random
import struct
import sys
import time

sys.path.insert(0, sys.path[0] or ".")
from ccsds_tools import (
    APIDS,
    CCSDS_TYPE_TC,
    OPCODES,
    build_primary_header,
    build_secondary_header,
    build_tc_frame,
    crc16_ccitt,
    parse_frame,
)


class Fuzzer:
    """CCSDS frame fuzzer with multiple mutation strategies."""

    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)
        self.cases: list[tuple[str, bytes]] = []

    def _add(self, name: str, frame: bytes):
        self.cases.append((name, frame))

    def fuzz_apid(self):
        """Fuzz APID field — try all interesting values."""
        interesting_apids = [
            0x000,
            0x001,
            0x020,
            0x021,
            0x030,
            0x031,
            0x040,
            0x539,  # SECRET_DEBUG
            0x7FF,  # IDLE
            0x400,
            0x7FE,  # Boundaries
        ]
        # Add random APIDs
        for _ in range(10):
            interesting_apids.append(self.rng.randint(0, 0x7FF))

        for apid in interesting_apids:
            frame = build_tc_frame(apid, bytes([OPCODES["NOP"]]))
            self._add(f"apid=0x{apid:03X}", frame)

    def fuzz_opcode(self):
        """Fuzz opcode byte — try all 256 values."""
        for opcode in range(256):
            frame = build_tc_frame(APIDS["TC_COMMAND"], bytes([opcode]))
            self._add(f"opcode=0x{opcode:02X}", frame)

    def fuzz_length(self):
        """Fuzz payload length — undersized and oversized."""
        # Empty payload
        frame = build_tc_frame(APIDS["TC_COMMAND"], b"")
        self._add("length=0", frame)

        # Max payload
        frame = build_tc_frame(APIDS["TC_COMMAND"], b"\x00" * 220)
        self._add("length=220", frame)

        # Oversized (beyond CCSDS_MAX_FRAME)
        frame = build_tc_frame(APIDS["TC_COMMAND"], b"\x00" * 250)
        self._add("length=250_overflow", frame)

        # Mismatch: header says small, payload is big
        payload = b"\x41" * 100
        sec_hdr = build_secondary_header(0)
        data_length = 5  # Lie about size
        hdr = build_primary_header(CCSDS_TYPE_TC, APIDS["TC_COMMAND"], 1, data_length)
        frame = hdr + sec_hdr + payload
        crc = crc16_ccitt(frame)
        frame += struct.pack(">H", crc)
        self._add("length_mismatch", frame)

    def fuzz_sequence(self):
        """Fuzz sequence counter — boundaries and duplicates."""
        for seq in [0, 1, 0x3FFE, 0x3FFF]:
            frame = build_tc_frame(APIDS["TC_COMMAND"], bytes([OPCODES["PING"]]), seq=seq)
            self._add(f"seq={seq}", frame)

    def fuzz_payload_patterns(self):
        """Fuzz with known-dangerous payload patterns."""
        patterns = [
            ("all_zeros", b"\x00" * 32),
            ("all_ff", b"\xff" * 32),
            ("all_41", b"\x41" * 100),  # AAAA...
            ("format_string", b"%x%x%x%x%x%x%x%x%n"),
            ("format_string_s", b"%s%s%s%s%s%s%s%s"),
            ("format_7s", b"%7$s"),
            ("null_in_middle", b"\x42\x00\x00\x00\x42"),
            ("newlines", b"\x42\x0a\x0a\x0a\x0d\x0a"),
            ("long_string", b"B" * 200),
            ("shellcode_nop_sled", b"\x90" * 64 + b"\xcc"),
            ("negative_int16", struct.pack("<h", -1)),
            ("max_int32", struct.pack("<I", 0xFFFFFFFF)),
        ]
        for name, payload in patterns:
            opcode = OPCODES.get("TABLE_WRITE", 0x70)
            frame = build_tc_frame(APIDS["TC_COMMAND"], bytes([opcode]) + payload)
            self._add(f"payload_{name}", frame)

    def fuzz_crc(self):
        """Fuzz CRC — valid frames with bad CRC to test rejection."""
        frame = build_tc_frame(APIDS["TC_COMMAND"], bytes([OPCODES["PING"]]))
        # Zero CRC
        bad = frame[:-2] + b"\x00\x00"
        self._add("crc_zero", bad)
        # Inverted CRC
        bad = frame[:-2] + bytes([frame[-2] ^ 0xFF, frame[-1] ^ 0xFF])
        self._add("crc_inverted", bad)
        # Truncated (no CRC)
        self._add("crc_missing", frame[:-2])

    def fuzz_header_corruption(self):
        """Send frames with corrupted header fields."""
        frame = build_tc_frame(APIDS["TC_COMMAND"], bytes([OPCODES["PING"]]))
        # Wrong version
        bad = bytes([frame[0] | 0xE0]) + frame[1:]  # version=7
        self._add("version=7", bad)
        # Wrong type bit
        bad = bytes([frame[0] ^ 0x10]) + frame[1:]  # flip TC/TM
        self._add("type_flipped", bad)
        # No secondary header flag
        bad = bytes([frame[0] & ~0x08]) + frame[1:]
        self._add("no_sec_hdr_flag", bad)

    def run_all(self):
        """Generate all fuzz cases."""
        self.fuzz_apid()
        self.fuzz_opcode()
        self.fuzz_length()
        self.fuzz_sequence()
        self.fuzz_payload_patterns()
        self.fuzz_crc()
        self.fuzz_header_corruption()
        return self.cases


def offline_fuzz(seed: int | None = None, categories: list[str] | None = None):
    """Generate fuzz cases and print them."""
    fuzzer = Fuzzer(seed)

    if categories:
        for cat in categories:
            method = getattr(fuzzer, f"fuzz_{cat}", None)
            if method:
                method()
            else:
                print(f"[!] Unknown category: {cat}")
    else:
        fuzzer.run_all()

    print(f"[*] Generated {len(fuzzer.cases)} fuzz cases")
    print()
    for name, frame in fuzzer.cases:
        parsed = parse_frame(frame)
        crc_ok = parsed.get("crc_valid", False)
        print(f"  {name:30s} ({len(frame):3d} bytes) CRC={'OK' if crc_ok else 'BAD'}  {frame.hex()}")


def online_fuzz(port: str, seed: int | None = None, delay: float = 0.5):
    """Send fuzz cases to a CDC Radio port and monitor for crashes."""
    import serial

    fuzzer = Fuzzer(seed)
    fuzzer.run_all()

    ser = serial.Serial(port, 115200, timeout=2, dsrdtr=False, rtscts=False)
    time.sleep(0.5)

    print(f"[*] Sending {len(fuzzer.cases)} fuzz cases to {port}")
    print(f"[*] Delay: {delay}s between frames")
    print()

    for i, (name, frame) in enumerate(fuzzer.cases):
        sys.stdout.write(f"\r[{i + 1}/{len(fuzzer.cases)}] {name:30s} ")
        sys.stdout.flush()

        ser.reset_input_buffer()
        cmd = f"TX {frame.hex().upper()}\r\n"
        ser.write(cmd.encode("ascii"))
        ser.flush()

        time.sleep(delay)
        resp = ser.read(ser.in_waiting or 1)
        if resp:
            resp_str = resp.decode(errors="replace").strip()
            if resp_str:
                print(f"-> {resp_str[:80]}")

    ser.close()
    print(f"\n\n[*] Fuzzing complete. {len(fuzzer.cases)} cases sent.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  frame_fuzzer.py offline [--seed N] [--cat apid,opcode,...]")
        print("  frame_fuzzer.py online <port> [--seed N] [--delay N]")
        print()
        print("Categories: apid, opcode, length, sequence, payload_patterns, crc, header_corruption")
        print()
        print("Generate mutated CCSDS frames to test firmware parser robustness.")
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    seed = None
    delay = 0.5
    cats = None
    port = None

    i = 0
    positional = []
    while i < len(args):
        if args[i] == "--seed":
            seed = int(args[i + 1])
            i += 2
        elif args[i] == "--delay":
            delay = float(args[i + 1])
            i += 2
        elif args[i] == "--cat":
            cats = args[i + 1].split(",")
            i += 2
        else:
            positional.append(args[i])
            i += 1

    if cmd == "offline":
        offline_fuzz(seed, cats)
    elif cmd == "online":
        if not positional:
            print("[!] Need serial port")
            sys.exit(1)
        online_fuzz(positional[0], seed, delay)
