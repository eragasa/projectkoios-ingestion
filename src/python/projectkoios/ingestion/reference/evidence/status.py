"""Closed reference-evidence aggregate statuses."""

from enum import StrEnum


class ReferenceEvidenceContractStatus(StrEnum):
    """Lifecycle status encoded by the Proposed wire contract."""

    PROPOSED = "proposed"


class ReferenceEvidenceCompleteness(StrEnum):
    """Whether the record contains reusable complete producer evidence."""

    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    UNSUPPORTED = "unsupported"
