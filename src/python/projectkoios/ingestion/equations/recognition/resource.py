"""Exact equation-recognition resource identity."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class EquationRecognitionResource:
    """One exact bounded recognizer resource."""

    name: str
    path: str
    sha256: str
    byte_size: int

    def __post_init__(self) -> None:
        if not self.name or not self.path:
            raise ValueError("recognition resource identity must be complete")
        if not re.fullmatch(r"[0-9a-f]{64}", self.sha256):
            raise ValueError("recognition resource hash must be SHA-256")
        if self.byte_size <= 0:
            raise ValueError("recognition resource size must be positive")
