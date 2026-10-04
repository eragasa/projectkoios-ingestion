from __future__ import annotations

from enum import StrEnum


class TranscriptionStatus(StrEnum):
    PROPOSED = "proposed"
    PROPOSED_WITH_UNCERTAINTY = "proposed_with_uncertainty"
