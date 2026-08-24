#!/usr/bin/env python3
"""RF-03: Capture and replay CCSDS frames over LoRa.

Listens on a CDC Radio serial port for TM frames, saves them to a
capture file, and can replay them later. Demonstrates that without
anti-replay (Level 1-2), captured frames are accepted as valid.

At Level 3 (AES-CTR + seq counter), replayed frames are rejected
— participants must increment the sequence counter to bypass.
"""

import json
import struct
import sys
import time
from datetime import datetime

sys.path.insert(0, sys.path[0] or ".")
from ccsds_tools import decode_tm, parse_frame


def _extract_frame_hex(line: str):
    """Pull the frame hex out of one capture line, or None if it isn't a frame.

    Handles both `+RX <len>,<hex>` and the CatSniffer/ground-station format
    `RX: <hex> | RSSI: <n> | SNR: <n>`.
    """
    line = line.strip()
    if "+RX" in line:
        parts = line.split(",", 1)
        if len(parts) == 2:
            return parts[1].strip()
    elif "RX: " in line and " |" in line:
        try:
            start_idx = line.index("RX: ") + 4
            end_idx = line.index(" |")
            return line[start_idx:end_idx].strip()
        except ValueError:
            return None
    return None


def _frame_entry(frame_hex: str, ts: str = None):
    """Build a frame dict from hex, or None if the hex is invalid."""
    try:
        frame_bytes = bytes.fromhex(frame_hex)
        parsed = parse_frame(frame_bytes)
    except ValueError:
        return None
    return {
        "timestamp": ts or datetime.now().isoformat(),
        "hex": frame_hex,
        "length": len(frame_bytes),
        "type": parsed.get("type", "?"),
        "apid": parsed.get("apid", 0),
        "seq": parsed.get("seq_count", 0),
        "crc_valid": parsed.get("crc_valid", False),
    }


def load_frames(capture_file: str):
    """Load frames from a capture file.

    Accepts both the JSON produced by `capture` and the raw text log written
    by the CatSniffer (`catnip sniff lora ... -r file.txt`) or by the ground
    station, whose lines look like `RX: <hex> | RSSI: <n> | SNR: <n>`.
    """
    with open(capture_file) as f:
        content = f.read()

    # JSON capture (from this tool's `capture` command)
    try:
        return json.loads(content).get("frames", [])
    except (json.JSONDecodeError, ValueError):
        pass

    # Raw text log (from `catnip sniff lora -r ...`)
    frames = []
    for line in content.splitlines():
        frame_hex = _extract_frame_hex(line)
        if frame_hex:
            entry = _frame_entry(frame_hex)
            if entry:
                frames.append(entry)
    return frames


def capture(port: str, output: str = "capture.json", duration: float = 30.0):
    """Capture frames from a CDC Radio port."""
    import serial

    ser = serial.Serial(port, 115200, timeout=1, dsrdtr=False, rtscts=False)
    time.sleep(0.5)
    ser.reset_input_buffer()

    frames = []
    print(f"[*] Capturing on {port} for {duration}s... (Ctrl+C to stop)")
    print(f"[*] Output: {output}")

    start = time.time()
    buf = b""

    try:
        while time.time() - start < duration:
            chunk = ser.read(ser.in_waiting or 1)
            if not chunk:
                continue
            buf += chunk

            # Try to extract frames from buffer
            if b"\n" in buf:
                lines = buf.split(b"\n")
                buf = lines[-1]
                for line_bytes in lines[:-1]:
                    frame_hex = _extract_frame_hex(line_bytes.decode(errors="replace"))
                    if not frame_hex:
                        continue
                    entry = _frame_entry(frame_hex)
                    if not entry:
                        continue
                    frames.append(entry)
                    print(
                        f"[+] Frame #{len(frames)}: {entry['type']} "
                        f"APID=0x{entry['apid']:03X} "
                        f"seq={entry['seq']} "
                        f"CRC={'OK' if entry['crc_valid'] else 'FAIL'} "
                        f"({entry['length']} bytes)"
                    )

    except KeyboardInterrupt:
        print("\n[*] Capture stopped by user")

    ser.close()

    with open(output, "w") as f:
        json.dump({"capture_date": datetime.now().isoformat(), "frames": frames}, f, indent=2)
    print(f"\n[*] Captured {len(frames)} frames -> {output}")


def replay(port: str, capture_file: str, delay: float = 1.0, modify_seq: bool = False):
    """Replay captured frames to a CDC Radio port."""
    import serial

    frames = load_frames(capture_file)
    if not frames:
        print("[!] No frames in capture file")
        return

    print(f"[*] Loaded {len(frames)} frames from {capture_file}")

    ser = serial.Serial(port, 115200, timeout=2, dsrdtr=False, rtscts=False)
    time.sleep(0.5)
    ser.reset_input_buffer()

    for i, entry in enumerate(frames):
        frame = bytes.fromhex(entry["hex"])

        if modify_seq:
            # Increment sequence counter to bypass anti-replay
            seq_ctrl = struct.unpack(">H", frame[2:4])[0]
            seq_flags = (seq_ctrl >> 14) & 0x03
            old_seq = seq_ctrl & 0x3FFF
            new_seq = (old_seq + 1000 + i) & 0x3FFF
            new_seq_ctrl = (seq_flags << 14) | new_seq
            frame = frame[:2] + struct.pack(">H", new_seq_ctrl) + frame[4:]

            # Recalculate CRC
            from ccsds_tools import crc16_ccitt

            payload_end = len(frame) - 2
            new_crc = crc16_ccitt(frame[:payload_end])
            frame = frame[:payload_end] + struct.pack(">H", new_crc)

            print(f"[*] Frame {i + 1}/{len(frames)}: seq {old_seq} -> {new_seq}")
        else:
            print(f"[*] Frame {i + 1}/{len(frames)}: replaying as-is (APID=0x{entry['apid']:03X}, seq={entry['seq']})")

        cmd = f"TX {frame.hex().upper()}\r\n"
        ser.write(cmd.encode("ascii"))
        ser.flush()

        time.sleep(0.5)
        resp = ser.read(ser.in_waiting or 1)
        if resp:
            print(f"    Response: {resp.decode(errors='replace').strip()}")

        if i < len(frames) - 1:
            time.sleep(delay)

    ser.close()
    print(f"\n[*] Replayed {len(frames)} frames")


def analyze(capture_file: str):
    """Analyze a capture file — show frame details and patterns."""
    frames = load_frames(capture_file)
    print(f"[*] Capture: {capture_file}")
    print(f"[*] Frames: {len(frames)}")
    print()

    seq_counts = []
    apid_counts = {}

    for entry in frames:
        apid = entry.get("apid", 0)
        apid_counts[apid] = apid_counts.get(apid, 0) + 1
        seq_counts.append(entry.get("seq", 0))

        frame = bytes.fromhex(entry["hex"])
        decoded = decode_tm(frame)
        detail = ""
        if "decoded" in decoded:
            detail = f" -> {decoded['decoded']}"
        print(
            f"  [{entry['timestamp']}] {entry['type']} "
            f"APID=0x{apid:03X} seq={entry.get('seq', '?')} "
            f"CRC={'OK' if entry.get('crc_valid') else 'FAIL'}{detail}"
        )

    print(f"\n[*] APID distribution: { {f'0x{k:03X}': v for k, v in apid_counts.items()} }")
    if len(seq_counts) >= 2:
        diffs = [seq_counts[i + 1] - seq_counts[i] for i in range(len(seq_counts) - 1)]
        print(f"[*] Seq increments: {diffs[:20]}{'...' if len(diffs) > 20 else ''}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  replay_capture.py capture <port> [output.json] [duration_sec]")
        print("  replay_capture.py replay <port> <capture> [--modify-seq]")
        print("  replay_capture.py analyze <capture>")
        print()
        print("Capture TM frames from LoRa, analyze patterns, and replay them.")
        print("<capture> can be this tool's .json OR a CatSniffer text log")
        print("  (catnip sniff lora ... -r file.txt, lines 'RX: <hex> | RSSI | SNR').")
        print("Use --modify-seq to increment sequence counters (bypass Level 3 anti-replay).")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "capture":
        port = sys.argv[2]
        out = sys.argv[3] if len(sys.argv) > 3 else "capture.json"
        dur = float(sys.argv[4]) if len(sys.argv) > 4 else 30.0
        capture(port, out, dur)

    elif cmd == "replay":
        port = sys.argv[2]
        capfile = sys.argv[3]
        mod_seq = "--modify-seq" in sys.argv
        replay(port, capfile, modify_seq=mod_seq)

    elif cmd == "analyze":
        analyze(sys.argv[2])
