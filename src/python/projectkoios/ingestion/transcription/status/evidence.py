from __future__ import annotations

from enum import StrEnum


class TranscriptionEvidenceStatus(StrEnum):
    OBSERVED_SOURCE_TRANSFORM = "observed_source_transform"
    PROPOSED = "proposed"
    AMBIGUOUS = "ambiguous"
