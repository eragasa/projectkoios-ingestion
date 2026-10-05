"""Supported extraction projection equivalence proofs."""

from enum import StrEnum


class ExtractionProjectionEquivalenceKind(StrEnum):
    """Distinguish replay stability from independent target rebuild."""

    SAME_STORE_REPLAY = "same_store_replay"
    INDEPENDENT_REBUILD = "independent_rebuild"
