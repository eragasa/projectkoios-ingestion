"""Reading evidence resource-limit failures."""

from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)


class ReadingEvidenceLimitError(ReadingEvidenceError):
    """Raised when reading evidence exceeds a fixed domain bound."""
