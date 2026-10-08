"""Closed canonical reading limitation codes."""

from enum import StrEnum


class ReadingEvidenceLimitationCode(StrEnum):
    """Evidence limitations retained without repairing their sources."""

    UNREVIEWED_VISUAL_EVIDENCE = "unreviewed_visual_evidence"
    UNACCEPTED_EQUATION_EVIDENCE = "unaccepted_equation_evidence"
    MISSING_OPTIONAL_RECOGNITION = "missing_optional_recognition"
    INVALID_GEOMETRY_OMITTED = "invalid_geometry_omitted"
    UNPLACED_PRODUCER_EVIDENCE = "unplaced_producer_evidence"
