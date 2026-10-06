"""TableStructureEvidenceStatus table-structure domain object."""

from __future__ import annotations

from enum import StrEnum


class TableStructureEvidenceStatus(StrEnum):
    """Proposal status with no accepted or validated state."""

    PROPOSED = "proposed"
    AMBIGUOUS = "ambiguous"
