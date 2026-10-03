from __future__ import annotations

import pytest


@pytest.fixture
def png_bytes() -> bytes:
    ihdr = (
        b"\x00\x00\x00\x0dIHDR"
        b"\x00\x00\x00\x01"
        b"\x00\x00\x00\x01"
        b"\x08\x00\x00\x00\x00"
        b"\x00\x00\x00\x00"
    )
    iend = b"\x00\x00\x00\x00IEND\xaeB`\x82"
    return b"\x89PNG\r\n\x1a\n" + ihdr + iend


@pytest.fixture
def jpeg_bytes() -> bytes:
    return b"\xff\xd8\xff\xe0\x00\x00\xff\xd9"


@pytest.fixture
def webp_bytes() -> bytes:
    return b"RIFF" + (12).to_bytes(4, "little") + b"WEBPVP8 \x00\x00\x00\x00"
