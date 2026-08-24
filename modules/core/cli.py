"""
cli.py - Centralized FlatSat CLI implementation.

Mirrors the Electronic Cats CatSniffer architecture (catnip/modules/core/cli.py):
all Click commands, option decorators, groups, and subcommands are consolidated
in this single cohesive file.
"""

import json
import os
import platform
import struct
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import click

from modules.utils._version import __version__

from modules.core.session import (
    DEVICE_HELP,
    PORT_HELP,
    flatsat_get_devices,
    send_cmd,
    with_device,
)
from modules.utils.banner import print_banner
from modules.utils.output import (
    console,
    print_dim,
    print_empty_line,
    print_error,
    print_info,
    print_response,
    print_success,
    print_title,
    print_warning,
)
from modules.utils.tables import print_devices_table


# Force UTF-8 encoding on Windows to prevent UnicodeEncodeError in terminals
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ==============================================================================
# ROOT CLICK GROUP
# ==============================================================================

@click.group("flatsat", context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, "-V", "--version", prog_name="flatsat")
@click.option("-d", "--device", default=None, help=DEVICE_HELP)
@click.option("-p", "--port", default=None, help=PORT_HELP)
@click.pass_context
def cli(ctx, device, port):
    """FlatSat Host CLI: manage and configure your FlatSat boards easily."""
    ctx.obj = {"device": device, "port": port}


# ==============================================================================
# DEVICE & SYSTEM COMMANDS
# ==============================================================================

@cli.command("devices")
def devices():
    """List all connected FlatSat boards and their endpoints"""
    devs = flatsat_get_devices()
    if not devs:
        print_title("CONNECTED FLATSAT DEVICES")
        print_warning("No FlatSat devices detected.")
        return

    print_devices_table(devs)


@cli.command("status")
@with_device
def status(dev):
    """Read system status and firmware information"""
    print_title("SYSTEM STATUS")
    fw_version = send_cmd(dev, "fw_version")
    state = send_cmd(dev, "status")
    if fw_version:
        print_response(fw_version.strip())
    if state:
        print_response(state.strip())
    if not fw_version and not state:
        print_warning("No status response received from board.")


@cli.command("sensors")
@with_device
def sensors(dev):
    """Read live telemetry data from BME280 and LIS2DH sensors"""
    print_title("TELEMETRY SENSORS")
    output = send_cmd(dev, "sensors")
    if output:
        print_response(output.strip())
    else:
        print_error("Failed to retrieve sensor values.")


@cli.command("color")
@click.argument("r", type=click.IntRange(0, 255))
@click.argument("g", type=click.IntRange(0, 255))
@click.argument("b", type=click.IntRange(0, 255))
@with_device
def color(dev, r, g, b):
    """Set custom RGB color on the NeoPixel LED

    Each channel takes a value from 0 to 255:

    \b
        flatsat color 255 0 0
    """
    output = send_cmd(dev, f"color {r} {g} {b}")
    print_info(output.strip() if output else "RGB color set.")


@cli.command("difficulty")
@click.argument("value", required=False, type=click.IntRange(0, 3))
@with_device
def difficulty(dev, value):
    """Get or set workshop security/difficulty level"""
    if value is not None:
        output = send_cmd(dev, f"difficulty {value}")
        print_info(output.strip() if output else f"Security Level set to {value}")
    else:
        output = send_cmd(dev, "difficulty")
        print_info(f"Security Level: {output.strip() if output else '(no response)'}")


@cli.command("identify")
@with_device
def identify(dev):
    """Trigger board LED identification blink"""
    print_info("Identifying FlatSat board (blinking LEDs)...")
    send_cmd(dev, "identify")
    time.sleep(2.2)
    print_success("LED identification sequence completed.")


@cli.command("reboot")
@with_device
def reboot(dev):
    """Reboot the board into the BOOTSEL bootloader"""
    print_info("Rebooting device into BOOTSEL bootloader mode...")
    dev.send_shell_command("reboot", timeout=0.2)
    print_success("Command sent. Device should disconnect shortly.")


@cli.command("cmd")
@click.argument("raw")
@with_device
def cmd(dev, raw):
    """Send a raw shell command to the FlatSat console

    \b
        flatsat cmd "lora_config"
    """
    output = send_cmd(dev, raw)
    if output:
        print_response(output.strip())
    else:
        print_warning("No response received from board.")


@cli.command("console")
@with_device
def console_cmd(dev):
    """Open a persistent interactive serial console session with the FlatSat board."""
    print_success("Connected to FlatSat interactive console.")
    print_info("Type any command (e.g. status, identify, mode gs, flight nominal) and press Enter.")
    print_info("Type 'exit' or 'quit' to close the session.")
    print_empty_line()

    while True:
        try:
            prompt_str = "flatsat> "
            try:
                user_input = input(prompt_str)
            except (KeyboardInterrupt, EOFError):
                print_empty_line()
                print_info("Closing interactive console session...")
                break

            cmd_str = user_input.strip()
            if not cmd_str:
                continue

            if cmd_str.lower() in ("exit", "quit", "q"):
                print_info("Closing interactive console session...")
                break

            if cmd_str.lower() == "identify":
                print_info("Identifying FlatSat board (blinking LEDs)...")
                send_cmd(dev, "identify")
                time.sleep(2.2)
                print_success("LED identification sequence completed.")
                continue

            output = send_cmd(dev, cmd_str)
            if output:
                print_response(output)
            else:
                print_warning(f"No response received for '{cmd_str}'.")

        except Exception as e:
            print_warning(f"Console error: {e}")
            break


# ==============================================================================
# SATELLITE & RADIO CONFIGURATION COMMANDS
# ==============================================================================

MODE_SEQUENCES = {
    "mission": ["mode sat", "lora_mode ALL stream", "lora_apply ALL"],
    "sat": ["mode sat", "lora_mode ALL stream", "lora_apply ALL"],
    "ground_station": ["mode gs", "lora_mode ALL command", "lora_apply ALL"],
    "gs": ["mode gs", "lora_mode ALL command", "lora_apply ALL"],
    "raw": ["mode gs", "lora_mode ALL stream", "lora_apply ALL"],
}


@cli.command("mode")
@click.argument(
    "value",
    required=False,
    type=click.Choice(["mission", "sat", "ground_station", "gs", "raw", "tinygs"]),
)
@click.option("--profile", default="norbi", show_default=True, help="TinyGS profile to spoof (only with 'tinygs').")
@with_device
def mode(dev, value, profile):
    """Get or set satellite operation mode

    \b
        flatsat mode mission          # satellite role (radios stream)
        flatsat mode ground_station   # ground station role (radios command)
        flatsat mode raw              # gs firmware, radios stream
        flatsat mode tinygs --profile norbi
    """
    if not value:
        output = send_cmd(dev, "mode")
        if not output:
            output = send_cmd(dev, "status")
        print_info(f"Current role: {output.strip() if output else '(no response)'}")
        return

    if value == "tinygs":
        send_cmd(dev, "lora_mode ALL stream")
        output = send_cmd(dev, f"tinygs spoof {profile}")
        print_success(f"TinyGS spoofing '{profile}': {output.strip() if output else 'OK'}")
    else:
        for c in MODE_SEQUENCES[value]:
            output = send_cmd(dev, c)
            print_info(f"{c} -> {output.strip() if output else 'OK'}")
        print_success(f"Mode set to '{value}'.")

    print_info("Identifying the board that changed mode (blinking LEDs)...")
    ident = send_cmd(dev, "identify")
    if ident:
        print_info(ident.strip())


# Flight control opcodes & helper
from modules.core.constants import TC_OP_NOP, TC_OP_SET_DEBUG, TC_OP_SET_NOMINAL, TC_OP_SET_SAFE_MODE
from modules.core.shell_parser import parse_difficulty, parse_mode

FLIGHT_STATES = ["idle", "nominal", "safe", "debug"]
FLIGHT_OPCODES = {
    "idle": TC_OP_NOP,
    "nominal": TC_OP_SET_NOMINAL,
    "safe": TC_OP_SET_SAFE_MODE,
    "debug": TC_OP_SET_DEBUG,
}


def _detect_local_role(dev):
    mode_raw = dev.send_shell_command_full("mode")
    status_raw = dev.send_shell_command_full("status")
    m = parse_mode(mode_raw)

    if m == "satellite":
        local_mode = "satellite"
    elif status_raw and "Radio0: LoRa  mode=command" in status_raw:
        local_mode = "ground_station"
    elif m == "raw":
        local_mode = "raw" if (status_raw and "mode=stream" in status_raw) else "ground_station"
    else:
        local_mode = m

    if local_mode in ("ground_station", "gs") or (getattr(dev, "has_radio1", True) and local_mode not in ("satellite", "mission")):
        return "ground_station"
    return "satellite" if local_mode in ("satellite", "mission") else "ground_station"


def _send_flight_over_rf(dev, value, difficulty):
    from modules.core.ccsds import sdls_protect_frame
    from modules.core.radio_bridge import RadioBridge
    from modules.core.state import GroundStationState
    from modules.core.telecommand import build_command_tc

    frame = build_command_tc(FLIGHT_OPCODES[value])
    frame = sdls_protect_frame(frame, difficulty)

    gs = GroundStationState()
    gs.set_hardware(dev)
    gs.difficulty = difficulty

    return RadioBridge(gs).send_raw(frame)


@cli.command("flight")
@click.argument("value", required=False, type=click.Choice(FLIGHT_STATES))
@click.option(
    "--difficulty",
    "difficulty_override",
    type=click.IntRange(0, 3),
    default=None,
    help="SDLS level for the RF telecommand (ground station only). Defaults to the board's difficulty.",
)
@with_device
def flight(dev, value, difficulty_override):
    """Get or set flight operational state (idle, nominal, safe, debug)

    \b
        flatsat flight                    # query current flight state
        flatsat flight nominal            # satellite: set connected board to NOMINAL
        flatsat flight nominal            # ground station: send NOMINAL as an RF telecommand
        flatsat flight safe --difficulty 3
    """
    if not value:
        output = send_cmd(dev, "flight")
        print_info(f"Flight State: {output.strip() if output else '(no response)'}")
        return

    role = _detect_local_role(dev)

    if role != "ground_station":
        output = send_cmd(dev, f"flight {value}")
        print_success(f"Flight state set to '{value}': {output.strip() if output else 'OK'}")
        return

    if difficulty_override is not None:
        diff = difficulty_override
    else:
        diff = parse_difficulty(dev.send_shell_command_full("difficulty"))

    print_info(f"Ground station detected. Sending flight TC '{value}' over RF (SDLS level {diff})...")
    result = _send_flight_over_rf(dev, value, diff)

    if result.get("status") == "error":
        print_error(f"Flight TC failed: {result.get('error')}")
        return

    detail = f" ({result.get('bytes', 0)} bytes, {result.get('response', 'OK')})" if result.get("status") == "sent" else ""
    print_success(f"Flight TC '{value}' transmitted over RF{detail}.")
    if result.get("status") == "sent_simulated":
        print_warning("Transmitted in simulated mode (no radio hardware).")


def _fmt_cfg(res):
    return res.strip() if res else "OK"


@cli.command("config")
@click.option("--radio", type=click.Choice(["0", "1", "ALL", "all"]), default="0", show_default=True, help="Radio index to configure (0, 1, or ALL)")
@click.option("--freq", type=int, help="LoRa frequency in Hz (e.g. 915000000)")
@click.option("--sf", type=click.IntRange(7, 12), help="Spreading Factor (7-12)")
@click.option("--bw", type=click.Choice(["125", "250", "500"]), help="Bandwidth in kHz")
@click.option("--cr", type=click.IntRange(5, 8), help="Coding Rate (5-8)")
@click.option("--power", type=click.IntRange(-9, 22), help="TX power in dBm (-9 to 22)")
@click.option("--preamble", type=click.IntRange(6, 65535), help="Preamble length (6-65535)")
@click.option("--iq", type=click.Choice(["normal", "inverted"]), help="IQ polarity")
@click.option("--syncword", help="Syncword (public, private, or hex value e.g. 0x2D)")
@click.option("--mode", type=click.Choice(["stream", "command"]), help="LoRa output mode (applied immediately)")
@click.option("--apply", is_flag=True, help="Apply staged changes immediately")
@with_device
def config(dev, radio, freq, sf, bw, cr, power, preamble, iq, syncword, mode, apply):
    """Stage and apply LoRa radio configuration settings

    \b
        flatsat config --radio 0 --freq 915000000 --sf 7 --apply
    """
    rp = f"R{radio}" if radio in ("0", "1") else "ALL"
    print_title(f"RADIO CONFIGURATION - TARGET {rp}")

    print_info(f"Configuring target {rp}")

    staged = False
    if freq is not None:
        res = send_cmd(dev, f"lora_freq {rp} {freq}")
        print_dim(f"Frequency        -> {freq} Hz: {_fmt_cfg(res)}")
        staged = True
    if sf is not None:
        res = send_cmd(dev, f"lora_sf {rp} {sf}")
        print_dim(f"Spreading Factor -> SF{sf}: {_fmt_cfg(res)}")
        staged = True
    if bw is not None:
        res = send_cmd(dev, f"lora_bw {rp} {bw}")
        print_dim(f"Bandwidth        -> {bw} kHz: {_fmt_cfg(res)}")
        staged = True
    if cr is not None:
        res = send_cmd(dev, f"lora_cr {rp} {cr}")
        print_dim(f"Coding Rate      -> 4/{cr}: {_fmt_cfg(res)}")
        staged = True
    if power is not None:
        res = send_cmd(dev, f"lora_power {rp} {power}")
        print_dim(f"Power            -> {power} dBm: {_fmt_cfg(res)}")
        staged = True
    if preamble is not None:
        res = send_cmd(dev, f"lora_preamble {rp} {preamble}")
        print_dim(f"Preamble         -> {preamble}: {_fmt_cfg(res)}")
        staged = True
    if iq is not None:
        res = send_cmd(dev, f"lora_iq {rp} {iq}")
        print_dim(f"IQ Polarity      -> {iq}: {_fmt_cfg(res)}")
        staged = True
    if syncword is not None:
        res = send_cmd(dev, f"lora_syncword {rp} {syncword}")
        print_dim(f"Syncword         -> {syncword}: {_fmt_cfg(res)}")
        staged = True
    if mode is not None:
        res = send_cmd(dev, f"lora_mode {rp} {mode}")
        print_success(f"Mode (Immediate) -> {mode}: {_fmt_cfg(res)}")

    if apply or staged:
        if apply:
            apply_res = send_cmd(dev, f"lora_apply {rp}")
            print_success(f"Applying changes: {_fmt_cfg(apply_res)}")
        else:
            print_warning("Changes are STAGED but not yet applied. Run with --apply to write to hardware.")
    elif mode is None:
        cfg_res = send_cmd(dev, f"lora_config {rp}")
        if cfg_res:
            print_response(cfg_res.strip())


# ==============================================================================
# RF SNIFFER, REPLAY & TRANSMIT COMMANDS
# ==============================================================================

def _frame_entry(parsed_rx, difficulty):
    from modules.core.ccsds import parse_frame, sdls_unprotect_frame

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


@cli.command("sniff")
@click.option("-r", "--radio", type=click.Choice(["0", "1"]), default="0",
              help="Radio to listen on: 0 = telemetry downlink (default), 1 = telecommand uplink.")
@click.option("-t", "--duration", type=float, default=30.0,
              help="Seconds to listen. Use 0 to run until Ctrl+C.")
@click.option("-o", "--output", type=click.Path(dir_okay=False), default=None,
              help="Write captured frames to this JSON file.")
@click.option("-n", "--count", type=int, default=0,
              help="Stop after capturing this many frames (0 = no limit).")
@click.option("--difficulty", "difficulty_override", type=click.IntRange(0, 3), default=None,
              help="SDLS level used to decrypt payloads. Defaults to the board's difficulty.")
@with_device
def sniff(dev, radio, duration, output, count, difficulty_override):
    """Sniff CCSDS frames over LoRa and optionally save them to a file

    \b
        flatsat sniff                                  # listen 30s on Radio 0
        flatsat sniff -t 0 -o capture.json             # capture until Ctrl+C
    """
    from modules.core.ccsds import detect_tm_difficulty
    from modules.core.device import parse_lora_rx

    radio_idx = int(radio)
    if radio_idx == 1 and not getattr(dev, "has_radio1", True):
        print_error("Radio 1 is not physically available on this board.")
        return

    detected_diff = difficulty_override
    if detected_diff is None:
        try:
            detected_diff = parse_difficulty(dev.send_shell_command_full("difficulty"))
        except Exception:
            detected_diff = 0

    label = "telemetry downlink" if radio_idx == 0 else "telecommand uplink"
    limit = f", stop after {count} frames" if count else ""
    window = "until Ctrl+C" if duration <= 0 else f"for {duration:g}s"
    print_info(f"Sniffing Radio {radio_idx} ({label}) {window} (SDLS level {detected_diff}){limit}...")
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

            # Auto-detect remote satellite difficulty if not forced
            if difficulty_override is None:
                try:
                    raw_preview = bytes.fromhex(parsed_rx["data"])
                    auto_d = detect_tm_difficulty(raw_preview)
                    if auto_d is not None and auto_d != detected_diff:
                        detected_diff = auto_d
                except Exception:
                    pass

            entry = _frame_entry(parsed_rx, detected_diff if detected_diff is not None else 0)
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
            with open(output, "w", encoding="utf-8") as f:
                json.dump({"capture_date": datetime.now().isoformat(), "frames": frames}, f, indent=2)
        except OSError as e:
            print_error(f"Failed to write {output}: {e}")
            return
        print_success(f"Captured {len(frames)} frames -> {output}")
    else:
        print_info(f"Captured {len(frames)} frames (no --output given, nothing saved).")


def _load_frames(capture_file):
    from modules.core.device import parse_lora_rx

    with open(capture_file, "r", encoding="utf-8") as f:
        content = f.read()

    try:
        return [e["hex"] for e in json.loads(content).get("frames", []) if e.get("hex")]
    except (json.JSONDecodeError, ValueError):
        pass

    hexes = []
    for line in content.splitlines():
        line_clean = line.strip()
        if not line_clean or line_clean.startswith("#"):
            continue
        parsed = parse_lora_rx(line_clean)
        if parsed:
            hexes.append(parsed["data"])
        elif all(c in "0123456789abcdefABCDEF" for c in line_clean) and len(line_clean) >= 12:
            hexes.append(line_clean)
    return hexes


def _bump_seq(frame, index):
    from modules.core.ccsds import build_seq_ctrl, ccsds_crc16, parse_seq_ctrl

    flags, old_seq = parse_seq_ctrl(struct.unpack(">H", frame[2:4])[0])
    new_seq = (old_seq + 1000 + index) & 0x3FFF
    frame = frame[:2] + struct.pack(">H", build_seq_ctrl(new_seq, flags)) + frame[4:]
    # Update timestamp in MET secondary header if present (length >= 12)
    if len(frame) >= 12:
        now_ts = int(time.time()) & 0xFFFFFFFF
        frame = frame[:6] + struct.pack(">I", now_ts) + frame[10:]
    frame = frame[:-2] + struct.pack(">H", ccsds_crc16(frame[:-2]))
    return frame, old_seq, new_seq


@cli.command("replay")
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
    """
    from modules.core.ccsds import sdls_protect_frame
    from modules.core.radio_bridge import RadioBridge
    from modules.core.state import GroundStationState

    hexes = _load_frames(capture_file)
    if not hexes:
        print_warning(f"No frames found in {capture_file}.")
        return

    if difficulty_override is not None:
        diff = difficulty_override
    else:
        diff = parse_difficulty(dev.send_shell_command_full("difficulty"))

    gs = GroundStationState()
    gs.set_hardware(dev)
    gs.difficulty = diff
    bridge = RadioBridge(gs)

    print_info(f"Loaded {len(hexes)} frames from {capture_file}. Replaying over RF (SDLS level {diff})...")

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

        result = bridge.send_raw(sdls_protect_frame(frame, diff))

        st = result.get("status")
        if st == "error":
            print_error(f"Frame {i + 1}/{len(hexes)}: {result.get('error')}")
        elif st == "sent_simulated":
            print_warning(f"Frame {i + 1}/{len(hexes)}: transmitted in simulated mode (no radio hardware).")
            sent += 1
        else:
            print_success(f"Frame {i + 1}/{len(hexes)}: sent ({result.get('bytes', 0)} bytes, {result.get('response', 'OK')})")
            sent += 1

        if i < len(hexes) - 1:
            time.sleep(delay)

    print_success(f"Replayed {sent}/{len(hexes)} frames.")


def _encode_payload(data, as_text):
    if as_text:
        return data.encode("utf-8")
    return bytes.fromhex(data.replace(" ", ""))


@cli.command("transmit")
@click.argument("data")
@click.option("--text", "as_text", is_flag=True, help="Interpret DATA as plain ASCII/UTF-8 text instead of hex.")
@click.option("--protect", is_flag=True, help="Apply SDLS protection before transmitting.")
@click.option("--repeat", type=click.IntRange(1), default=1, show_default=True, help="Number of times to transmit.")
@click.option("--delay", type=float, default=1.0, show_default=True, help="Seconds to wait between repeats.")
@click.option("--difficulty", "difficulty_override", type=click.IntRange(0, 3), default=None,
              help="SDLS level applied when --protect is set.")
@with_device
def transmit(dev, data, as_text, protect, repeat, delay, difficulty_override):
    """Transmit a custom hex or text string over RF

    \b
        flatsat transmit 1af0c30500ab            # send a raw hex frame
        flatsat transmit --text "HELLO SAT"      # send plain ASCII bytes
    """
    from modules.core.ccsds import build_tc, parse_frame, sdls_protect_frame
    from modules.core.constants import APID_TC_COMMAND
    from modules.core.radio_bridge import RadioBridge
    from modules.core.state import GroundStationState

    try:
        raw_payload = _encode_payload(data, as_text)
    except ValueError:
        print_error("Invalid hex string. Use --text to send plain text, or pass valid hex.")
        return

    if not raw_payload:
        print_warning("Empty payload, nothing to transmit.")
        return

    if difficulty_override is not None:
        diff = difficulty_override
    else:
        diff = parse_difficulty(dev.send_shell_command_full("difficulty"))

    gs = GroundStationState()
    gs.set_hardware(dev)
    gs.difficulty = diff
    bridge = RadioBridge(gs)

    kind = "text" if as_text else "hex"
    sdls = f" (SDLS level {diff})" if protect else " (raw, no SDLS)"
    print_info(f"Transmitting {len(raw_payload)} bytes from {kind} string over RF{sdls}...")

    sent = 0
    for i in range(repeat):
        ts = int(time.time()) & 0xFFFFFFFF
        pkt = parse_frame(raw_payload) if len(raw_payload) >= 12 else None

        if protect:
            if pkt is not None and pkt.pkt_type == 1 and pkt.sec_hdr_flag == 1:
                frame_to_send = sdls_protect_frame(raw_payload, diff)
            else:
                seq = (int(time.time() * 10) + i) & 0x3FFF or 1
                tc_frame = build_tc(APID_TC_COMMAND, raw_payload, seq_count=seq, timestamp=ts)
                frame_to_send = sdls_protect_frame(tc_frame, diff)
        else:
            frame_to_send = raw_payload

        result = bridge.send_raw(frame_to_send)
        label = f"Transmission {i + 1}/{repeat}: " if repeat > 1 else ""

        st = result.get("status")
        if st == "error":
            print_error(f"{label}{result.get('error')}")
        elif st == "sent_simulated":
            print_warning(f"{label}transmitted in simulated mode (no radio hardware).")
            sent += 1
        else:
            print_success(f"{label}sent ({result.get('bytes', 0)} bytes, {result.get('response', 'OK')})")
            sent += 1

        if i < repeat - 1:
            time.sleep(delay)

    if repeat > 1:
        print_success(f"Transmitted payload {sent}/{repeat} times.")


# ==============================================================================
# TAB COMPLETION COMMAND GROUP
# ==============================================================================

@cli.group("completion", context_settings={"help_option_names": ["-h", "--help"]})
def completion():
    """Install shell tab completion for flatsat."""


@completion.command("install")
@click.option(
    "--shell",
    type=click.Choice(["bash", "zsh", "fish"]),
    default=None,
    help="Shell to install completion for (auto-detected if omitted).",
)
def completion_install(shell):
    """Install tab completion for your shell."""
    if platform.system() == "Windows":
        print_error("Shell completion is not supported on Windows.")
        sys.exit(1)

    if shell is None:
        shell_env = os.environ.get("SHELL", "")
        if "zsh" in shell_env:
            shell = "zsh"
        elif "fish" in shell_env:
            shell = "fish"
        elif "bash" in shell_env:
            shell = "bash"
        else:
            print_error("Could not detect shell. Use --shell bash|zsh|fish.")
            sys.exit(1)
        print_info(f"Detected shell: {shell}")

    script_abs = str(Path(sys.argv[0]).resolve())
    python_abs = sys.executable
    cmd_to_call = f"{python_abs} {script_abs}"
    prog_name = "flatsat"
    env_var = "_FLATSAT_COMPLETE"
    script_basename = "flatsat.py"

    if shell == "bash":
        target = Path.home() / ".local" / "share" / "bash-completion" / "completions" / prog_name
        source_flag = "bash_source"
        rc_note = None
    elif shell == "zsh":
        target = Path.home() / ".zfunc" / f"_{prog_name}"
        source_flag = "zsh_source"
        rc_note = "fpath=(~/.zfunc $fpath)\nautoload -Uz compinit && compinit"
    elif shell == "fish":
        target = Path.home() / ".config" / "fish" / "completions" / f"{prog_name}.fish"
        source_flag = "fish_source"
        rc_note = None

    root_dir = str(Path(__file__).resolve().parent.parent.parent)
    env = {**os.environ, env_var: source_flag, "PYTHONPATH": root_dir + os.pathsep + os.environ.get("PYTHONPATH", "")}

    try:
        res = subprocess.run(
            [python_abs, script_abs],
            env=env,
            capture_output=True,
            text=True,
        )
        comp_script = res.stdout
    except Exception as e:
        print_error(f"Failed to generate completion script: {e}")
        sys.exit(1)

    if not comp_script.strip():
        print_error("Empty completion script generated.")
        sys.exit(1)

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(comp_script)
    print_success(f"Completion script written to: {target}")

    if rc_note:
        zshrc = Path.home() / ".zshrc"
        existing = zshrc.read_text() if zshrc.exists() else ""
        if ".zfunc" not in existing:
            with zshrc.open("a") as f:
                f.write(f"\n# flatsat tab completion\n{rc_note}\n")
            print_success(f"Added fpath entry to {zshrc}")

    print_empty_line()
    if shell == "bash":
        print_info("Restart your shell or run:")
        print_dim(f"source {target}")
    elif shell == "zsh":
        print_info("Restart your shell or run:")
        print_dim("source ~/.zshrc && compinit -u")


# ==============================================================================
# ENTRY POINT
# ==============================================================================

def main_cli() -> None:
    main()


def main() -> None:
    if not os.environ.get("_FLATSAT_COMPLETE"):
        module = next((a for a in sys.argv[1:] if not a.startswith("-")), None)
        print_banner(module)
    cli(prog_name="flatsat")


__all__ = [
    "cli",
    "devices",
    "status",
    "sensors",
    "color",
    "difficulty",
    "identify",
    "reboot",
    "cmd",
    "console_cmd",
    "mode",
    "flight",
    "config",
    "sniff",
    "replay",
    "transmit",
    "completion",
    "main",
    "main_cli",
    "_detect_local_role",
]


if __name__ == "__main__":
    main_cli()
