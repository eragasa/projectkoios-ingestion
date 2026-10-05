"""Typed extraction projection inventory equivalence differences."""

from enum import StrEnum


class ExtractionProjectionInventoryMismatch(StrEnum):
    """Classify provenance, collection-set, and content differences."""

    TARGET = "target"
    CONFIGURATION = "configuration"
    SCHEMA = "schema"
    COLLECTION_SET = "collection_set"
    COLLECTION_CONTENT = "collection_content"
    REPLAY_MATERIALIZATION = "replay_materialization"
