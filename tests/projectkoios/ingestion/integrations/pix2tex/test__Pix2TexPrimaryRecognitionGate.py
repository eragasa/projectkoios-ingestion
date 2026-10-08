from __future__ import annotations

import zlib

import pytest
from projectkoios.ingestion.integrations.pix2tex.policy import (
    _foreground_profile,
)


def _chunk(name: bytes, content: bytes) -> bytes:
    body = name + content
    return (
        len(content).to_bytes(4, "big")
        + body
        + (zlib.crc32(body) & 0xFFFFFFFF).to_bytes(4, "big")
    )


def _rgb_png(*, width: int, height: int, ink_rows: set[int]) -> bytes:
    rows = bytearray()
    for row in range(height):
        rows.append(0)
        value = 0 if row in ink_rows else 255
        rows.extend(bytes((value, value, value)) * width)
    header = (
        width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + bytes((8, 2, 0, 0, 0))
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(bytes(rows)))
        + _chunk(b"IEND", b"")
    )


def test__primary_recognition_gate__retains_one_isolated_band() -> None:
    content = _rgb_png(
        width=100,
        height=40,
        ink_rows=set(range(15, 25)),
    )

    assert _foreground_profile(content) == (1, 0.375, 0.375)


def test__primary_gate__identifies_overbroad_three_band_region() -> None:
    content = _rgb_png(
        width=100,
        height=60,
        ink_rows={*range(6, 11), *range(27, 32), *range(48, 53)},
    )

    band_count, top_margin, bottom_margin = _foreground_profile(content)

    assert band_count == 3
    assert top_margin == 0.1
    assert bottom_margin == pytest.approx(7 / 60)


def test__primary_recognition_gate__identifies_two_band_edge_contact() -> None:
    content = _rgb_png(
        width=100,
        height=40,
        ink_rows={*range(0, 5), *range(20, 25)},
    )

    band_count, top_margin, bottom_margin = _foreground_profile(content)

    assert band_count == 2
    assert top_margin == 0.0
    assert bottom_margin == 0.375
