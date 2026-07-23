"""Transmit a user-supplied string over RF.

Companion to `flatsat replay`: instead of reading frames from a capture file,
this lets the user hand-craft a single payload and transmit it through the same
TX path the rest of the CLI uses (core.radio_bridge.RadioBridge, like `flight`
and `replay`).

The string is interpreted as hex by default (a raw frame, matching how `replay`
stores/sends frames); pass --text to send it as plain ASCII/UTF-8 bytes instead.
By default the bytes are transmitted as-is; pass --protect to re-apply SDLS
protection at transmit time (matching `flight`/`replay`), treating the string as
a complete plaintext CCSDS frame.
"""

import time

import click

from cli.session import with_device
from cli.ui.output import print_error, print_info, print_success, print_warning
from core.shell_parser import parse_difficulty


def _encode_payload(data, as_text):
    """Turn the user's string into bytes, either as ASCII text or a hex frame."""
    if as_text:
        return data.encode("utf-8")
    return bytes.fromhex(data.replace(" ", ""))


@click.command("transmit")
@click.argument("data")
@click.option("--text", "as_text", is_flag=True,
              help="Interpret DATA as plain ASCII/UTF-8 text instead of hex.")
@click.option("--protect", is_flag=True,
              help="Apply SDLS protection before transmitting (treats DATA as a plaintext CCSDS frame).")
@click.option("--repeat", type=click.IntRange(1), default=1, show_default=True,
              help="Number of times to transmit the payload.")
@click.option("--delay", type=float, default=1.0, show_default=True,
              help="Seconds to wait between repeats.")
@click.option("--difficulty", "difficulty_override", type=click.IntRange(0, 3), default=None,
              help="SDLS level applied when --protect is set. Defaults to the board's difficulty.")
@with_device
def transmit(dev, data, as_text, protect, repeat, delay, difficulty_override):
    """Transmit a custom hex or text string over RF

    \b
        flatsat transmit 1af0c30500ab            # send a raw hex frame as-is
        flatsat transmit --text "HELLO SAT"      # send plain ASCII bytes
        flatsat transmit 1af0c305 --protect      # SDLS-protect a plaintext CCSDS frame
        flatsat transmit 1af0c305 --repeat 5 --delay 0.5
    """
    from core.ccsds import sdls_protect_frame
    from core.radio_bridge import RadioBridge
    from core.state import GroundStationState

    try:
        payload = _encode_payload(data, as_text)
    except ValueError:
        print_error("Invalid hex string. Use --text to send plain text, or pass valid hex.")
        return

    if not payload:
        print_warning("Empty payload, nothing to transmit.")
        return

    if difficulty_override is not None:
        difficulty = difficulty_override
    else:
        difficulty = parse_difficulty(dev.send_shell_command_full("difficulty"))

    if protect:
        payload = sdls_protect_frame(payload, difficulty)

    # Build a minimal hardware state so we transmit through the same path as the
    # webapp/`flight`/`replay`: RadioBridge reads device, active_radio and
    # difficulty from here.
    gs = GroundStationState()
    gs.set_hardware(dev)
    gs.difficulty = difficulty
    bridge = RadioBridge(gs)

    kind = "text" if as_text else "hex"
    sdls = f" (SDLS level {difficulty})" if protect else " (raw, no SDLS)"
    print_info(f"Transmitting {len(payload)} bytes from {kind} string over RF{sdls}...")

    sent = 0
    for i in range(repeat):
        result = bridge.send_raw(payload)
        label = f"Transmission {i + 1}/{repeat}: " if repeat > 1 else ""

        status = result.get("status")
        if status == "error":
            print_error(f"{label}{result.get('error')}")
        elif status == "sent_simulated":
            print_warning(f"{label}transmitted in simulated mode (no radio hardware).")
            sent += 1
        else:
            print_success(f"{label}sent ({result.get('bytes', 0)} bytes, {result.get('response', 'OK')})")
            sent += 1

        if i < repeat - 1:
            time.sleep(delay)

    if repeat > 1:
        print_success(f"Transmitted payload {sent}/{repeat} times.")
