"""Closed managed artifact media vocabulary."""

from enum import StrEnum


class ManagedArtifactMediaType(StrEnum):
    """Supported externally managed artifact media types."""

    APPLICATION_PDF = "application/pdf"
    IMAGE_JPEG = "image/jpeg"
    IMAGE_PNG = "image/png"
    IMAGE_WEBP = "image/webp"
