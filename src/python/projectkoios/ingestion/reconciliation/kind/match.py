"""OCRReconciliationMatchKind reconciliation domain object."""

from __future__ import annotations

from enum import StrEnum


class OCRReconciliationMatchKind(StrEnum):
    DUPLICATE = "duplicate"
    DISAGREEMENT = "disagreement"
