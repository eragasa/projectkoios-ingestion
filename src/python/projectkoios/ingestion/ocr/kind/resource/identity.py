"""OCRResourceIdentityKind OCR domain object."""

from __future__ import annotations

from enum import StrEnum


class OCRResourceIdentityKind(StrEnum):
    SHA256 = "sha256"
    EXPLICIT = "explicit"
