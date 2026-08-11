"""Sniff CCSDS frames off the air and optionally save them to a capture file.

Native equivalent of toolkit/replay_capture.py's `capture` command: listens on
a radio (Radio 0 = telemetry downlink by default, Radio 1 = telecommand uplink)
using the exact same RX path as the webapp telemetry loop — read_line_from_radio
-> parse_lora_rx -> sdls_unprotect_frame -> parse_frame — and writes a JSON file
whose schema is understood by `replay_capture.py replay/analyze`.
"""

import json
import time
from datetime import datetime

import click

from cli.session import with_device
from cli.ui.output import print_error, print_info, print_success, print_warning
from core.shell_parser import parse_difficulty


def _frame_entry(parsed_rx, difficulty):
    """Turn a parse_lora_rx() dict into a capture entry, or None if not a CCSDS frame.

    Mirrors the webapp RX loop: decrypt the payload for SDLS level >= 2 before
    parsing, and drop frames whose CRC is bad (unless the trailer is 0x0000).
    """
    from core.ccsds import parse_frame, sdls_unprotect_frame

    try:
        raw_bytes = bytes.fromhex(parsed_rx["data"])
    except ValueError:
        return None

    pkt = parse_frame(raw_bytes)
    if pkt is None:
        return None
    if not pkt.crc_valid and raw_bytes[-2:] != b"\x00\x00":
        return None

    if difficulty >= 2:
        raw_bytes = sdls_unprotect_frame(raw_bytes, difficulty)
        pkt = parse_frame(raw_bytes) or pkt

    return {
        "timestamp": datetime.now().isoformat(),
        "hex": raw_bytes.hex().upper(),
        "length": len(raw_bytes),
        "type": "TC" if pkt.pkt_type == 1 else "TM",
        "apid": pkt.apid,
        "seq": pkt.seq_count,
        "crc_valid": pkt.crc_valid,
        "rssi": parsed_rx.get("rssi"),
        "snr": parsed_rx.get("snr"),
    }


@click.command("sniff")
@click.option("-r", "--radio", type=click.Choice(["0", "1"]), default="0",
              help="Radio to listen on: 0 = telemetry downlink (default), 1 = telecommand uplink.")
@click.option("-t", "--duration", type=float, default=30.0,
              help="Seconds to listen. Use 0 to run until Ctrl+C.")
@click.option("-o", "--output", type=click.Path(dir_okay=False), default=None,
              help="Write captured frames to this JSON file (compatible with replay_capture.py).")
@click.option("-n", "--count", type=int, default=0,
              help="Stop after capturing this many frames (0 = no limit).")
@click.option("--difficulty", "difficulty_override", type=click.IntRange(0, 3), default=None,
              help="SDLS level used to decrypt payloads. Defaults to the board's difficulty.")
@with_device
def sniff(dev, radio, duration, output, count, difficulty_override):
    """Sniff CCSDS frames over LoRa and optionally save them to a file

    \b
        flatsat sniff                                  # listen 30s on Radio 0, print only
        flatsat sniff -t 0 -o capture.json             # capture until Ctrl+C into capture.json
        flatsat sniff -r 1 -n 10 -o uplink.json        # grab 10 telecommand frames
        replay_capture.py replay <port> capture.json   # replay what you captured
    """
    from core.device import parse_lora_rx

    radio_idx = int(radio)
    if difficulty_override is not None:
        difficulty = difficulty_override
    else:
        difficulty = parse_difficulty(dev.send_shell_command_full("difficulty"))

    label = "telemetry downlink" if radio_idx == 0 else "telecommand uplink"
    limit = f", stop after {count} frames" if count else ""
    window = "until Ctrl+C" if duration <= 0 else f"for {duration:g}s"
    print_info(f"Sniffing Radio {radio_idx} ({label}) {window} (SDLS level {difficulty}){limit}...")
    if output:
        print_info(f"Output: {output}")

    frames = []
    start = time.time()
    try:
        while duration <= 0 or time.time() - start < duration:
            line = dev.read_line_from_radio(radio_idx, timeout=1.0)
            if not line:
                continue
            parsed_rx = parse_lora_rx(line)
            if not parsed_rx:
                continue
            entry = _frame_entry(parsed_rx, difficulty)
            if not entry:
                continue
            frames.append(entry)
            rssi = entry["rssi"]
            print_success(
                f"#{len(frames)}: {entry['type']} APID=0x{entry['apid']:03X} "
                f"seq={entry['seq']} CRC={'OK' if entry['crc_valid'] else 'FAIL'} "
                f"({entry['length']} bytes"
                f"{f', RSSI {rssi}' if rssi is not None else ''})"
            )
            if count and len(frames) >= count:
                break
    except KeyboardInterrupt:
        print_warning("Sniffing stopped by user.")

    if not frames:
        print_warning("No CCSDS frames captured. Is the satellite transmitting on this radio?")
        return

    if output:
        try:
            with open(output, "w") as f:
                json.dump({"capture_date": datetime.now().isoformat(), "frames": frames}, f, indent=2)
        except OSError as e:
            print_error(f"Failed to write {output}: {e}")
            return
        print_success(f"Captured {len(frames)} frames -> {output}")
    else:
        print_info(f"Captured {len(frames)} frames (no --output given, nothing saved).")
