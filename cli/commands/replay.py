"""Replay captured CCSDS frames back over RF.

Native equivalent of toolkit/replay_capture.py's `replay` command, wired
through the same TX path the rest of the CLI uses (core.radio_bridge.RadioBridge,
just like `flight`). Loads a capture file produced by `flatsat sniff` (or a raw
`RX: <hex> | ...` text log) and retransmits each frame.

Frames captured by `flatsat sniff` are stored as plaintext CCSDS; this command
re-applies SDLS protection at transmit time (matching `flight`), so the replay
is valid at any difficulty. Use --modify-seq to bump the sequence counter and
bypass the Level 3 anti-replay window.
"""

import json
import struct
import time

import click

from cli.session import with_device
from cli.ui.output import print_error, print_info, print_success, print_warning
from core.shell_parser import parse_difficulty


def _load_frames(capture_file):
    """Load frame hex strings from a capture file.

    Accepts the JSON written by `flatsat sniff`/`replay_capture.py capture`
    (a `{"frames": [{"hex": ...}]}` object) and the raw `RX: <hex> | RSSI | SNR`
    text logs, returning a list of hex strings.
    """
    from core.device import parse_lora_rx

    with open(capture_file) as f:
        content = f.read()

    try:
        return [e["hex"] for e in json.loads(content).get("frames", []) if e.get("hex")]
    except (json.JSONDecodeError, ValueError):
        pass

    hexes = []
    for line in content.splitlines():
        parsed = parse_lora_rx(line.strip())
        if parsed:
            hexes.append(parsed["data"])
    return hexes


def _bump_seq(frame, index):
    """Increment the sequence counter (and fix the CRC) to bypass anti-replay."""
    from core.ccsds import build_seq_ctrl, ccsds_crc16, parse_seq_ctrl

    flags, old_seq = parse_seq_ctrl(struct.unpack(">H", frame[2:4])[0])
    new_seq = (old_seq + 1000 + index) & 0x3FFF
    frame = frame[:2] + struct.pack(">H", build_seq_ctrl(new_seq, flags)) + frame[4:]
    frame = frame[:-2] + struct.pack(">H", ccsds_crc16(frame[:-2]))
    return frame, old_seq, new_seq


@click.command("replay")
@click.argument("capture_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--delay", type=float, default=1.0, help="Seconds to wait between frames.")
@click.option("--modify-seq", is_flag=True, help="Increment sequence counters to bypass Level 3 anti-replay.")
@click.option("--difficulty", "difficulty_override", type=click.IntRange(0, 3), default=None,
              help="SDLS level applied when transmitting. Defaults to the board's difficulty.")
@with_device
def replay(dev, capture_file, delay, modify_seq, difficulty_override):
    """Replay captured CCSDS frames from a file back over RF

    \b
        flatsat replay capture.json                 # replay every frame as-is
        flatsat replay capture.json --modify-seq    # bump seq counters (bypass L3)
        flatsat replay uplink.json --delay 0.5 --difficulty 3
    """
    from core.ccsds import sdls_protect_frame
    from core.radio_bridge import RadioBridge
    from core.state import GroundStationState

    hexes = _load_frames(capture_file)
    if not hexes:
        print_warning(f"No frames found in {capture_file}.")
        return

    if difficulty_override is not None:
        difficulty = difficulty_override
    else:
        difficulty = parse_difficulty(dev.send_shell_command_full("difficulty"))

    # Build a minimal hardware state so we transmit through the same path as the
    # webapp/`flight`: RadioBridge reads device, active_radio and difficulty here.
    gs = GroundStationState()
    gs.set_hardware(dev)
    gs.difficulty = difficulty
    bridge = RadioBridge(gs)

    print_info(f"Loaded {len(hexes)} frames from {capture_file}. Replaying over RF (SDLS level {difficulty})...")

    sent = 0
    for i, frame_hex in enumerate(hexes):
        try:
            frame = bytes.fromhex(frame_hex)
        except ValueError:
            print_warning(f"Frame {i + 1}/{len(hexes)}: invalid hex, skipping.")
            continue

        if modify_seq:
            frame, old_seq, new_seq = _bump_seq(frame, i)
            print_info(f"Frame {i + 1}/{len(hexes)}: seq {old_seq} -> {new_seq}")

        result = bridge.send_raw(sdls_protect_frame(frame, difficulty))

        status = result.get("status")
        if status == "error":
            print_error(f"Frame {i + 1}/{len(hexes)}: {result.get('error')}")
        elif status == "sent_simulated":
            print_warning(f"Frame {i + 1}/{len(hexes)}: transmitted in simulated mode (no radio hardware).")
            sent += 1
        else:
            print_success(f"Frame {i + 1}/{len(hexes)}: sent ({result.get('bytes', 0)} bytes, {result.get('response', 'OK')})")
            sent += 1

        if i < len(hexes) - 1:
            time.sleep(delay)

    print_success(f"Replayed {sent}/{len(hexes)} frames.")
