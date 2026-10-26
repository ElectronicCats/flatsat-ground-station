#!/usr/bin/env python3
"""Generate the application icon (assets/flatsat-gs.ico) without dependencies.

Pure standard library: a 32x32 and a 48x48 32-bit BMP inside an ICO
container, plus a 256x256 PNG for the macOS .app bundle.

The mark is a satellite: a dark body, two solar panels and an orbit ring,
in the PWNLAB green.

    python scripts/make_icon.py
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"

# ── Palette (BGR + alpha) ───────────────────────────────────────────────────
TRANSPARENT = (0, 0, 0, 0)
BODY_DARK = (0x1B, 0x2A, 0x38, 255)  # BGR
BODY_EDGE = (0x2E, 0x45, 0x5A, 255)
GREEN = (0x41, 0xFF, 0x00, 255)  # PWNLAB green (BGR: 41 FF 00)
GREEN_DIM = (0x00, 0xA8, 0x2B, 255)
WHITE = (0xFF, 0xFF, 0xFF, 255)


def _blend(dst, src):
    """Alpha-composite src over dst."""
    sa = src[3] / 255.0
    if sa >= 1.0:
        return src
    if sa <= 0.0:
        return dst
    return tuple(
        int(src[i] * sa + dst[i] * (1 - sa)) if i != 3 else int(src[3] * sa + dst[3] * (1 - sa)) for i in range(4)
    )


def _draw(size: int) -> list[list[tuple[int, int, int, int]]]:
    """Render the icon as a size x size grid of BGRA pixels."""
    px = [[TRANSPARENT for _ in range(size)] for _ in range(size)]
    c = (size - 1) / 2.0
    r_out = size * 0.46
    r_in = size * 0.40

    # Solar panels: two tilted rectangles on the sides of the body.
    panel_h = size * 0.30
    panel_w = size * 0.26
    body_w = size * 0.20
    body_h = size * 0.36

    for y in range(size):
        for x in range(size):
            fx, fy = x - c, y - c
            dist = (fx * fx + fy * fy) ** 0.5

            # Orbit ring
            if r_in <= dist <= r_out:
                ring = GREEN if (dist - r_in) / (r_out - r_in) > 0.35 else GREEN_DIM
                px[y][x] = _blend(px[y][x], ring)

            # Body
            if abs(fx) <= body_w / 2 and abs(fy) <= body_h / 2:
                edge = abs(fx) > body_w / 2 - max(1.0, size * 0.04)
                px[y][x] = _blend(px[y][x], BODY_EDGE if edge else BODY_DARK)

            # Solar panels (one on each side of the body)
            for lo, hi in (
                (-(body_w / 2 + panel_w), -body_w / 2),
                (body_w / 2, body_w / 2 + panel_w),
            ):
                if lo <= fx < hi and abs(fy) <= panel_h / 2:
                    # Panel grid lines
                    line = (int(fx) % max(2, int(size * 0.10)) == 0) or (int(fy) % max(2, int(size * 0.13)) == 0)
                    px[y][x] = _blend(px[y][x], GREEN_DIM if line else BODY_EDGE)

            # Signal beacon on top of the body
            if abs(fx) <= size * 0.06 and -(body_h / 2 + size * 0.06) <= fy <= -body_h / 2:
                px[y][x] = _blend(px[y][x], WHITE)

    return px


def _bmp_image(px: list[list[tuple[int, int, int, int]]]) -> bytes:
    """Encode the grid as an ICO BMP entry (32-bit BGRA + AND mask)."""
    size = len(px)
    header = struct.pack(
        "<IiiHHIIiiII",
        40,  # biSize
        size,  # biWidth
        size * 2,  # biHeight (XOR + AND)
        1,  # biPlanes
        32,  # biBitCount
        0,  # biCompression
        0,  # biSizeImage
        0,
        0,
        0,
        0,  # ppm
    )
    # XOR bitmap: bottom-up rows
    xor = bytearray()
    for y in range(size - 1, -1, -1):
        for x in range(size):
            b, g, r, a = px[y][x]
            xor += bytes((b, g, r, a))

    # AND mask: 1 bit per pixel, rows padded to 4 bytes
    and_mask = bytearray()
    row_bytes = ((size + 31) // 32) * 4
    for y in range(size - 1, -1, -1):
        row = bytearray(row_bytes)
        for x in range(size):
            if px[y][x][3] == 0:
                row[x // 8] |= 0x80 >> (x % 8)
        and_mask += row

    return header + bytes(xor) + bytes(and_mask)


def _png_image(px: list[list[tuple[int, int, int, int]]]) -> bytes:
    """Encode the grid as a PNG (used for the macOS bundle)."""
    size = len(px)
    raw = bytearray()
    for y in range(size):
        raw.append(0)  # filter type: none
        for x in range(size):
            b, g, r, a = px[y][x]
            raw += bytes((r, g, b, a))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
    )


def build_ico(sizes: tuple[int, ...] = (16, 32, 48, 64, 256)) -> bytes:
    images = []
    for size in sizes:
        if size == 256:
            images.append(_png_image(_draw(256)))
        else:
            images.append(_bmp_image(_draw(size)))

    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = bytearray()
    for size, data in zip(sizes, images, strict=True):
        entries += struct.pack(
            "<BBBBHHII",
            0 if size >= 256 else size,  # 0 means 256
            0 if size >= 256 else size,
            0,  # palette
            0,  # reserved
            1,  # planes
            32,  # bpp
            len(data),
            offset,
        )
        offset += len(data)
    return header + bytes(entries) + b"".join(images)


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    ico_path = ASSETS / "flatsat-gs.ico"
    ico_path.write_bytes(build_ico())
    print(f"[+] {ico_path} ({ico_path.stat().st_size} bytes)")

    png_path = ASSETS / "flatsat-gs.png"
    png_path.write_bytes(_png_image(_draw(512)))
    print(f"[+] {png_path} ({png_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
