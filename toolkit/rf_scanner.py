#!/usr/bin/env python3
"""RF-01: LoRa frequency scanner — find the satellite's downlink frequency.

Scans a range of frequencies by reconfiguring the ground station radio
via shell commands, then listens for TM frames on each frequency.

Participants use this to discover the satellite's operating frequency
when it's not known (or after a SET_FREQ attack changes it).
"""

import sys
import time

sys.path.insert(0, sys.path[0] or ".")
from ccsds_tools import parse_frame

# Common LoRa frequencies (Hz) for ISM bands
ISM_FREQUENCIES = [
    # 915 MHz band (Americas)
    915000000,
    916000000,
    917000000,
    918000000,
    919000000,
    920000000,
    921000000,
    922000000,
    923000000,
    924000000,
    925000000,
    # 868 MHz band (Europe)
    868000000,
    868500000,
    869000000,
    869500000,
    870000000,
    # 433 MHz band
    433000000,
    434000000,
    435000000,
    436000000,
    436703000,
    # TinyGS common
    437700000,
]

SPREADING_FACTORS = [7, 8, 9, 10, 11, 12]
BANDWIDTHS = [125000, 250000, 500000]


def shell_command(ser, cmd: str, wait: float = 0.5) -> str:
    """Send a command to the FlatSat shell and return the response."""
    ser.reset_input_buffer()
    ser.write(f"{cmd}\r\n".encode())
    ser.flush()
    time.sleep(wait)
    resp = ser.read(ser.in_waiting or 1)
    return resp.decode(errors="replace").strip()


def set_frequency(ser, freq_hz: int) -> bool:
    """Set the radio frequency via shell lora_config command."""
    resp = shell_command(ser, f"lora_config freq {freq_hz}", wait=0.3)
    return "ok" in resp.lower() or "freq" in resp.lower()


def set_spreading_factor(ser, sf: int) -> bool:
    """Set the LoRa spreading factor."""
    resp = shell_command(ser, f"lora_config sf {sf}", wait=0.3)
    return "ok" in resp.lower() or "sf" in resp.lower()


def set_bandwidth(ser, bw: int) -> bool:
    """Set the LoRa bandwidth."""
    resp = shell_command(ser, f"lora_config bw {bw}", wait=0.3)
    return "ok" in resp.lower() or "bw" in resp.lower()


def listen_for_frames(ser, duration: float = 3.0) -> list[bytes]:
    """Listen on the radio port for incoming frames."""
    frames = []
    buf = b""
    start = time.time()

    while time.time() - start < duration:
        chunk = ser.read(ser.in_waiting or 1)
        if chunk:
            buf += chunk
            # Parse +RX responses
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
                        frames.append(frame)
                    except ValueError:
                        pass
        time.sleep(0.05)

    return frames


def scan_frequencies(
    shell_port: str,
    radio_port: str,
    frequencies: list[int] | None = None,
    listen_time: float = 3.0,
    sf: int | None = None,
    bw: int | None = None,
):
    """Scan frequencies and report which ones have satellite traffic."""
    import serial

    if frequencies is None:
        frequencies = ISM_FREQUENCIES

    shell = serial.Serial(shell_port, 115200, timeout=1, dsrdtr=False, rtscts=False)
    radio = serial.Serial(radio_port, 115200, timeout=1, dsrdtr=False, rtscts=False)
    time.sleep(1)

    if sf is not None:
        print(f"[*] Setting SF={sf}")
        set_spreading_factor(shell, sf)
    if bw is not None:
        print(f"[*] Setting BW={bw}")
        set_bandwidth(shell, bw)

    print(f"[*] Scanning {len(frequencies)} frequencies ({listen_time}s per freq)...")
    print(f"[*] Estimated time: {len(frequencies) * (listen_time + 0.5):.0f}s")
    print()

    results = []

    for i, freq in enumerate(frequencies):
        freq_mhz = freq / 1e6
        sys.stdout.write(f"\r[{i + 1}/{len(frequencies)}] {freq_mhz:.3f} MHz ... ")
        sys.stdout.flush()

        set_frequency(shell, freq)
        time.sleep(0.2)

        frames = listen_for_frames(radio, listen_time)

        if frames:
            valid = sum(1 for f in frames if parse_frame(f).get("crc_valid"))
            print(f"FOUND! {len(frames)} frames ({valid} valid CRC)")
            for frame in frames[:3]:
                p = parse_frame(frame)
                apid_hex = f"0x{p.get('apid', 0):03X}"
                print(f"    APID={apid_hex} seq={p.get('seq_count', '?')} CRC={'OK' if p.get('crc_valid') else 'FAIL'}")
            results.append((freq, len(frames), valid))
        else:
            print("silent")

    shell.close()
    radio.close()

    print(f"\n{'=' * 50}")
    print("[*] Scan Results:")
    if results:
        for freq, total, valid in sorted(results, key=lambda x: -x[1]):
            print(f"  {freq / 1e6:.3f} MHz: {total} frames ({valid} valid)")
    else:
        print("  No frames detected on any frequency.")
        print("  Try: different SF/BW, longer listen time, or check antenna.")


def quick_scan(shell_port: str, radio_port: str):
    """Quick scan of the most common FlatSat frequencies."""
    common = [915000000, 916000000, 868500000, 436703000, 433000000]
    print("[*] Quick scan: checking most common frequencies")
    scan_frequencies(shell_port, radio_port, common, listen_time=5.0)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  rf_scanner.py scan <shell_port> <radio_port> [--sf N] [--bw N] [--time N]")
        print("  rf_scanner.py quick <shell_port> <radio_port>")
        print("  rf_scanner.py range <shell_port> <radio_port> <start_mhz> <end_mhz> <step_mhz>")
        print()
        print("Scan LoRa frequencies to find the satellite's downlink.")
        print("Requires two serial ports: shell (for lora_config) and radio (for RX).")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "quick":
        quick_scan(sys.argv[2], sys.argv[3])

    elif cmd == "scan":
        shell_p = sys.argv[2]
        radio_p = sys.argv[3]
        sf = bw = None
        listen = 3.0
        args = sys.argv[4:]
        i = 0
        while i < len(args):
            if args[i] == "--sf":
                sf = int(args[i + 1])
                i += 2
            elif args[i] == "--bw":
                bw = int(args[i + 1])
                i += 2
            elif args[i] == "--time":
                listen = float(args[i + 1])
                i += 2
            else:
                i += 1
        scan_frequencies(shell_p, radio_p, listen_time=listen, sf=sf, bw=bw)

    elif cmd == "range":
        shell_p = sys.argv[2]
        radio_p = sys.argv[3]
        start = int(float(sys.argv[4]) * 1e6)
        end = int(float(sys.argv[5]) * 1e6)
        step = int(float(sys.argv[6]) * 1e6)
        freqs = list(range(start, end + 1, step))
        scan_frequencies(shell_p, radio_p, freqs)
