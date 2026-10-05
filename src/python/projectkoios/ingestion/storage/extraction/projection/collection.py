"""Logical collections in the extraction read model."""

from enum import StrEnum


class ExtractionProjectionCollection(StrEnum):
    """Backend-neutral role of one projected extraction document."""

    BLOCKS = "blocks"
    DOCUMENTS = "documents"
    MANIFESTS = "manifests"
    PAGES = "pages"
    WARNINGS = "warnings"
