"""Closed inventory fields used by reading evidence reconciliation."""

from enum import StrEnum


class ReadingEvidenceInventoryField(StrEnum):
    """Complete comparable current-contract inventory field names."""

    PAGE_COUNT = "page_count"
    STREAM_COUNT = "stream_count"
    SELECTION_COUNT = "selection_count"
    BLOCK_COUNT = "block_count"
    PARAGRAPH_COUNT = "paragraph_count"
    HEADING_COUNT = "heading_count"
    FIGURE_COUNT = "figure_count"
    TABLE_COUNT = "table_count"
    EQUATION_COUNT = "equation_count"
    CAPTION_COUNT = "caption_count"
    GATE_COUNT = "gate_count"
    ASSOCIATION_COUNT = "association_count"
    ARTIFACT_COUNT = "artifact_count"
    CHARACTER_COUNT = "character_count"
    UTF8_BYTE_COUNT = "utf8_byte_count"
    LIMITATION_COUNT = "limitation_count"
    PAGES_SHA256 = "pages_sha256"
    BLOCKS_SHA256 = "blocks_sha256"
    PRODUCERS_SHA256 = "producers_sha256"
    ARTIFACTS_SHA256 = "artifacts_sha256"
    LIMITATIONS_SHA256 = "limitations_sha256"
    LINEAGE_ID = "lineage_id"
