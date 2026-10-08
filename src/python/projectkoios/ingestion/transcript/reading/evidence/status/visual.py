"""Closed visual reading evidence states."""

from enum import StrEnum


class ReadingVisualEvidenceStatus(StrEnum):
    """Vendor-neutral visual evidence state."""

    PROPOSED = "proposed"
    AMBIGUOUS = "ambiguous"
    OBSERVED = "observed"
