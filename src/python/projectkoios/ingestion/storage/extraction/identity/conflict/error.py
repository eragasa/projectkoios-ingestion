"""Extraction publication identity-conflict failure."""

from projectkoios.ingestion.storage.extraction.error import (
    ExtractionPublicationError,
)


class ExtractionPublicationIdentityConflictError(ExtractionPublicationError):
    """Report valid identities bound to conflicting publication content."""
