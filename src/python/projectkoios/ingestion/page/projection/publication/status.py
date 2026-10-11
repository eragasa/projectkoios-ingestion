"""Closed publication profile and operation disposition vocabularies."""

from enum import StrEnum


class PageProjectionPublicationProfile(StrEnum):
    """Owner-supported deterministic publication profiles."""

    NATIVE_PDF_TEXT_V1 = "native-pdf-text-v1"


class PageProjectionPublicationDisposition(StrEnum):
    """Successful durable publication operation dispositions."""

    CREATED = "created"
    REPLAYED_IDENTICAL = "replayed_identical"
