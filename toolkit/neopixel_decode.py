#!/usr/bin/env python3
"""MS-07: Neopixel covert channel decoder.

The FlatSat can transmit data via Neopixel LED color sequences using
the NEOPIXEL_RAW opcode (0xA0). Each LED color encodes data bits:
- Red channel: high nibble
- Green channel: low nibble
- Blue channel: checksum/sync

This tool decodes captured color sequences back into data, either from:
- Manual input (color values observed visually)
- Video capture (frame-by-frame color extraction)
- Logic analyzer captures of the WS2812B data line
"""

import json
import sys

# Neopixel encoding scheme (matches firmware neopixel_covert.c)
# Each byte is split into two nibbles, sent as two LED updates:
#   High nibble -> Red channel (0-15 mapped to 0-255)
#   Low nibble  -> Green channel (0-15 mapped to 0-255)
#   Blue channel -> frame sync (0xFF = start, 0x00 = data, 0x80 = end)

NIBBLE_SCALE = 17  # 0-15 -> 0-255 (255/15 = 17)
SYNC_START = 0xFF
SYNC_DATA = 0x00
SYNC_END = 0x80


def decode_colors(colors: list[tuple[int, int, int]]) -> bytes:
    """Decode a sequence of (R, G, B) tuples into bytes.

    Each pair of colors encodes one byte:
    - First color:  R = high nibble, G = low nibble
    - Blue channel indicates frame position
    """
    data = bytearray()
    in_frame = False

    for r, g, b in colors:
        if b == SYNC_START:
            in_frame = True
            continue
        elif b == SYNC_END:
            in_frame = False
            continue

        if not in_frame and b != SYNC_DATA:
            continue

        # Extract nibbles
        high = min(r // NIBBLE_SCALE, 15)
        low = min(g // NIBBLE_SCALE, 15)
        byte_val = (high << 4) | low
        data.append(byte_val)

    return bytes(data)


def encode_message(message: bytes) -> list[tuple[int, int, int]]:
    """Encode a message into neopixel color sequence."""
    colors = []

    # Start sync
    colors.append((0, 0, SYNC_START))

    # Data
    for byte in message:
        high = (byte >> 4) & 0x0F
        low = byte & 0x0F
        colors.append((high * NIBBLE_SCALE, low * NIBBLE_SCALE, SYNC_DATA))

    # End sync
    colors.append((0, 0, SYNC_END))

    return colors


def from_manual_input():
    """Interactive mode: enter observed RGB values."""
    print("[*] Enter RGB values one per line (R,G,B format)")
    print("[*] Enter 'done' when finished")
    print()

    colors = []
    while True:
        try:
            line = input(f"  Color #{len(colors) + 1}: ").strip()
        except EOFError:
            break
        if line.lower() in ("done", "q", "quit", ""):
            break
        try:
            parts = line.replace("(", "").replace(")", "").split(",")
            r, g, b = int(parts[0].strip()), int(parts[1].strip()), int(parts[2].strip())
            colors.append((r, g, b))
        except (ValueError, IndexError):
            print("    [!] Invalid format. Use: R,G,B (e.g., 255,0,0)")

    if colors:
        data = decode_colors(colors)
        print(f"\n[*] Decoded {len(data)} bytes:")
        print(f"    Hex: {data.hex()}")
        print(f"    ASCII: {data.decode('ascii', errors='replace')}")

        # Check for flags
        decoded = data.decode("ascii", errors="replace")
        if "PWNSAT{" in decoded:
            start = decoded.index("PWNSAT{")
            end = decoded.index("}", start) + 1
            print(f"    [FLAG] {decoded[start:end]}")


def from_json(filepath: str):
    """Decode from a JSON file with color arrays.

    Expected format: {"colors": [[R,G,B], [R,G,B], ...]}
    """
    with open(filepath) as f:
        data = json.load(f)

    colors = [tuple(c) for c in data.get("colors", data if isinstance(data, list) else [])]
    if not colors:
        print("[!] No colors found in JSON")
        return

    print(f"[*] Loaded {len(colors)} colors from {filepath}")
    decoded = decode_colors(colors)
    print(f"[*] Decoded {len(decoded)} bytes:")
    print(f"    Hex: {decoded.hex()}")
    print(f"    ASCII: {decoded.decode('ascii', errors='replace')}")

    decoded_str = decoded.decode("ascii", errors="replace")
    if "PWNSAT{" in decoded_str:
        start = decoded_str.index("PWNSAT{")
        end = decoded_str.index("}", start) + 1
        print(f"    [FLAG] {decoded_str[start:end]}")


def from_ws2812_logic(filepath: str):
    """Decode WS2812B data line capture from logic analyzer CSV.

    WS2812B protocol: each bit is a timed pulse
    - 0 bit: ~350ns high, ~800ns low
    - 1 bit: ~700ns high, ~600ns low
    - Reset: >50us low

    24 bits per LED: G[7:0] R[7:0] B[7:0] (GRB order)
    """
    import csv

    print(f"[*] Parsing WS2812B capture: {filepath}")

    # Read timing data
    edges = []
    with open(filepath) as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = float(row.get("Time [s]", row.get("time", 0)))
            val = int(row.get("Value", row.get("data", row.get("Channel 0", 0))))
            edges.append((ts, val))

    if not edges:
        print("[!] No data in capture")
        return

    # Extract bits from timing
    bits = []
    i = 0
    while i < len(edges) - 1:
        if edges[i][1] == 1:  # Rising edge
            # Find falling edge
            j = i + 1
            while j < len(edges) and edges[j][1] != 0:
                j += 1
            if j < len(edges):
                high_time = edges[j][0] - edges[i][0]
                # Classify bit
                if high_time < 0.5e-6:
                    bits.append(0)
                else:
                    bits.append(1)
            i = j + 1
        else:
            # Check for reset (long low)
            if i + 1 < len(edges):
                low_time = edges[i + 1][0] - edges[i][0]
                if low_time > 50e-6:
                    bits.append("RESET")
            i += 1

    # Group into bytes (8 bits each), then into LED colors (3 bytes = GRB)
    colors = []
    current_bits = []
    for bit in bits:
        if bit == "RESET":
            current_bits = []
            continue
        current_bits.append(bit)
        if len(current_bits) == 24:
            g = sum(b << (7 - i) for i, b in enumerate(current_bits[0:8]))
            r = sum(b << (7 - i) for i, b in enumerate(current_bits[8:16]))
            b_val = sum(b << (7 - i) for i, b in enumerate(current_bits[16:24]))
            colors.append((r, g, b_val))
            current_bits = []

    print(f"[*] Extracted {len(colors)} LED colors")
    for i, (r, g, b) in enumerate(colors):
        print(f"    LED {i}: R={r:3d} G={g:3d} B={b:3d}")

    if colors:
        decoded = decode_colors(colors)
        print(f"\n[*] Decoded {len(decoded)} bytes:")
        print(f"    Hex: {decoded.hex()}")
        print(f"    ASCII: {decoded.decode('ascii', errors='replace')}")


def demo():
    """Encode and decode a sample message to demonstrate the protocol."""
    message = b"PWNSAT{NEOPIXEL_COVERT}"
    print(f"[*] Demo: encoding '{message.decode()}'")
    print()

    colors = encode_message(message)
    print(f"[*] Encoded into {len(colors)} LED updates:")
    for i, (r, g, b) in enumerate(colors):
        sync = "START" if b == SYNC_START else "END" if b == SYNC_END else "DATA"
        print(f"    #{i:2d}: R={r:3d} G={g:3d} B={b:3d}  [{sync}]")

    print()
    decoded = decode_colors(colors)
    print(f"[*] Decoded back: {decoded.decode('ascii', errors='replace')}")
    assert decoded == message, "Round-trip failed!"
    print("[+] Round-trip OK")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  neopixel_decode.py manual             Enter RGB values interactively")
        print("  neopixel_decode.py json <colors.json>  Decode from JSON color array")
        print("  neopixel_decode.py ws2812 <capture.csv> Decode WS2812B logic capture")
        print("  neopixel_decode.py encode <message>    Encode a message to colors")
        print("  neopixel_decode.py demo                Show encoding/decoding example")
        print()
        print("Decode covert channel data transmitted via Neopixel LED color sequences.")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "manual":
        from_manual_input()
    elif cmd == "json":
        from_json(sys.argv[2])
    elif cmd == "ws2812":
        from_ws2812_logic(sys.argv[2])
    elif cmd == "encode":
        msg = " ".join(sys.argv[2:]).encode()
        colors = encode_message(msg)
        print(f"[*] Encoded '{msg.decode()}':")
        print(json.dumps({"colors": colors}, indent=2))
    elif cmd == "demo":
        demo()
