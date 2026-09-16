from __future__ import annotations

import argparse
import hashlib
import struct
import zlib
from pathlib import Path

FIXTURE_PATH = Path("tests/fixtures/ocr/synthetic-text.png")
TEXT = "KOIOS OCR 42"
WIDTH = 148
HEIGHT = 22
SCALE = 2
GLYPHS = {
    " ": ("00000",) * 7,
    "2": (
        "01110",
        "10001",
        "00001",
        "00010",
        "00100",
        "01000",
        "11111",
    ),
    "4": (
        "00010",
        "00110",
        "01010",
        "10010",
        "11111",
        "00010",
        "00010",
    ),
    "C": (
        "01111",
        "10000",
        "10000",
        "10000",
        "10000",
        "10000",
        "01111",
    ),
    "I": (
        "11111",
        "00100",
        "00100",
        "00100",
        "00100",
        "00100",
        "11111",
    ),
    "K": (
        "10001",
        "10010",
        "10100",
        "11000",
        "10100",
        "10010",
        "10001",
    ),
    "O": (
        "01110",
        "10001",
        "10001",
        "10001",
        "10001",
        "10001",
        "01110",
    ),
    "R": (
        "11110",
        "10001",
        "10001",
        "11110",
        "10100",
        "10010",
        "10001",
    ),
    "S": (
        "01111",
        "10000",
        "10000",
        "01110",
        "00001",
        "00001",
        "11110",
    ),
}


def _chunk(kind: bytes, payload: bytes) -> bytes:
    checksum = zlib.crc32(kind + payload) & 0xFFFFFFFF
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", checksum)
    )


def fixture_bytes() -> bytes:
    pixels = bytearray(b"\xff\xff\xff" * WIDTH * HEIGHT)
    cursor_x = 2
    origin_y = 4
    for character in TEXT:
        glyph = GLYPHS[character]
        for row_index, row in enumerate(glyph):
            for column_index, bit in enumerate(row):
                if bit == "0":
                    continue
                for dy in range(SCALE):
                    for dx in range(SCALE):
                        x = cursor_x + column_index * SCALE + dx
                        y = origin_y + row_index * SCALE + dy
                        offset = (y * WIDTH + x) * 3
                        pixels[offset : offset + 3] = b"\x00\x00\x00"
        cursor_x += 6 * SCALE
    rows = b"".join(
        b"\x00" + pixels[y * WIDTH * 3 : (y + 1) * WIDTH * 3]
        for y in range(HEIGHT)
    )
    ihdr = struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(rows, level=9))
        + _chunk(b"IEND", b"")
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--refresh", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    expected = fixture_bytes()
    if args.refresh:
        FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE_PATH.write_bytes(expected)
        print(
            f"wrote {FIXTURE_PATH} "
            f"sha256={hashlib.sha256(expected).hexdigest()}"
        )
        return 0
    if not FIXTURE_PATH.is_file():
        raise SystemExit(f"missing fixture: {FIXTURE_PATH}")
    actual = FIXTURE_PATH.read_bytes()
    if actual != expected:
        raise SystemExit(
            f"fixture mismatch: {FIXTURE_PATH}; run with --refresh"
        )
    print(
        f"verified {FIXTURE_PATH} sha256={hashlib.sha256(actual).hexdigest()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
