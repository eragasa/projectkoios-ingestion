"""Reference-evidence domain failures."""


class ReferenceEvidenceError(ValueError):
    """Base error for the bounded reference-evidence projection."""


class ReferenceEvidenceParseError(ReferenceEvidenceError):
    """Raised when external reference-evidence bytes are not canonical."""


class ReferenceEvidenceVerificationError(ReferenceEvidenceError):
    """Raised when evidence is unusable or does not match expected bytes."""
