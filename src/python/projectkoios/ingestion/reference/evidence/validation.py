"""Bounded requirements for immutable reference-evidence values."""

from dataclasses import dataclass

from projectkoios.ingestion.reference.evidence.limits.definition import (
    REFERENCE_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.reference.evidence.limits.error import (
    ReferenceEvidenceLimitError,
)
from projectkoios.ingestion.sha256.hash import SHA256Hash


@dataclass(frozen=True, slots=True)
class ReferenceEvidenceValueRequirements:
    """Apply one explicit string ceiling to evidence record values."""

    maximum_string_characters: int

    def __post_init__(self) -> None:
        if (
            type(self.maximum_string_characters) is not int
            or self.maximum_string_characters < 1
        ):
            raise ValueError(
                "maximum_string_characters must be a positive built-in int"
            )

    def require_text(self, value: object, name: str) -> str:
        """Return one nonempty bounded UTF-8 string."""
        if not isinstance(value, str) or not value:
            raise ValueError(f"{name} must be a non-empty string")
        if len(value) > self.maximum_string_characters:
            raise ReferenceEvidenceLimitError(
                f"{name} exceeds the string limit"
            )
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeEncodeError as error:
            raise ValueError(f"{name} must be valid UTF-8") from error
        return value

    def require_nonnegative_int(self, value: object, name: str) -> int:
        """Return one nonnegative built-in integer."""
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")
        return value

    def require_sha256(self, value: object, name: str) -> str:
        """Return one canonical lowercase SHA-256 digest."""
        digest = self.require_text(value, name)
        if not SHA256Hash.is_canonical(digest):
            raise ValueError(f"{name} must be a lowercase SHA-256 digest")
        return digest


REFERENCE_EVIDENCE_VALUE_REQUIREMENTS = ReferenceEvidenceValueRequirements(
    maximum_string_characters=REFERENCE_EVIDENCE_LIMITS.maximum_string_characters
)
