"""Closed enrichment styles, bases, outcomes, and detail states."""

from enum import StrEnum


class PageProjectionEvidenceStyle(StrEnum):
    """Retain the exact projected block style without importing Search."""

    PARAGRAPH = "paragraph"
    HEADING = "heading"
    FIGURE_CAPTION = "figure_caption"


class PageProjectionEvidenceRetainedTextBasis(StrEnum):
    """Identify the only exact retained-text construction admitted in v1."""

    TEXT_BLOCK_RAW_SOURCE_SEQUENCE = "text_block_raw_source_sequence"


class PageProjectionEvidenceUnavailableReason(StrEnum):
    """Explain why one projected block has no admissible v1 enrichment."""

    FIGURE_CAPTION_HAS_NO_EXACT_RAW_CLEAN_PAIR = (
        "figure_caption_has_no_exact_raw_clean_pair"
    )


class PageProjectionEvidenceWarningDetailStatus(StrEnum):
    """State whether producer-owned warning detail is retained."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
