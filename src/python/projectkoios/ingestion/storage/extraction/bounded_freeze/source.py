"""Exact source bytes and private locator returned by a source reader."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExtractionSourceMaterial:
    """Ephemeral source material; never retained in an action result."""

    content: bytes
    locator: str

    def __post_init__(self) -> None:
        if type(self.content) is not bytes or not self.content:
            raise ValueError("extraction source content must be nonempty bytes")
        if type(self.locator) is not str or not self.locator:
            raise ValueError("extraction source locator must be nonempty")
