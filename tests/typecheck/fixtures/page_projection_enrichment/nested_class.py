from __future__ import annotations

from dataclasses import dataclass


def build_identity() -> type[object]:
    @dataclass(frozen=True, slots=True)
    class NestedIdentity:
        value: str

    return NestedIdentity
