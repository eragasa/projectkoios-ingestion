"""Supported backend-neutral reading-evidence equivalence proofs."""

from enum import StrEnum


class ReadingEvidenceEquivalenceKind(StrEnum):
    """Distinguish exact replay from independent source reconstruction."""

    SAME_STORE_REPLAY = "same_store_replay"
    INDEPENDENT_REBUILD = "independent_rebuild"
