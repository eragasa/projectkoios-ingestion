"""Closed clean-text transformation kinds."""

from enum import StrEnum


class ReadingTextTransformationKind(StrEnum):
    """Closed clean-text transformation vocabulary."""

    DEHYPHENATION = "dehyphenation"
    GLYPH_SUBSTITUTION = "glyph_substitution"
    PAGE_ARTIFACT_REMOVAL = "page_artifact_removal"
    UNICODE_NORMALIZATION = "unicode_normalization"
    WHITESPACE_NORMALIZATION = "whitespace_normalization"
