"""Extraction publication failures."""


class ExtractionPublicationError(RuntimeError):
    """Raised when an extraction publication cannot be safely committed."""
