"""Reference-evidence resource-limit failures."""

from projectkoios.ingestion.reference.evidence.error import (
    ReferenceEvidenceError,
)


class ReferenceEvidenceLimitError(ReferenceEvidenceError):
    """Raised before reference-evidence processing exceeds a hard bound."""
