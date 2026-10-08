"""State-bound strict field access for reference-evidence JSON values."""

from dataclasses import dataclass
from enum import StrEnum

from projectkoios.ingestion.json.value import JsonValue
from projectkoios.ingestion.reference.evidence.limits.error import (
    ReferenceEvidenceLimitError,
)
from projectkoios.ingestion.reference.evidence.validation import (
    REFERENCE_EVIDENCE_VALUE_REQUIREMENTS,
    ReferenceEvidenceValueRequirements,
)


@dataclass(frozen=True, slots=True)
class ReferenceEvidenceJsonValueReader:
    """Read exact typed fields using explicit evidence value requirements."""

    requirements: ReferenceEvidenceValueRequirements

    def mapping(
        self,
        value: JsonValue,
        name: str,
        fields: set[str],
    ) -> dict[str, JsonValue]:
        """Return one object with exactly the required field names."""
        if not isinstance(value, dict):
            raise TypeError(f"{name} must be an object")
        if any(not isinstance(key, str) for key in value):
            raise TypeError(f"{name} field names must be strings")
        actual = set(value)
        unknown = actual - fields
        missing = fields - actual
        if unknown:
            raise ValueError(f"{name} has unknown fields: {sorted(unknown)}")
        if missing:
            raise ValueError(f"{name} is missing fields: {sorted(missing)}")
        return value

    def array(
        self,
        value: JsonValue,
        name: str,
        maximum: int,
    ) -> list[JsonValue]:
        """Return one array within its wire-object item ceiling."""
        if not isinstance(value, list):
            raise TypeError(f"{name} must be an array")
        if len(value) > maximum:
            raise ReferenceEvidenceLimitError(f"{name} exceeds the item limit")
        return value

    def text(self, value: JsonValue, name: str) -> str:
        """Return one bounded text field."""
        return self.requirements.require_text(value, name)

    def integer(self, value: JsonValue, name: str) -> int:
        """Return one nonnegative integer field."""
        return self.requirements.require_nonnegative_int(value, name)

    def boolean(self, value: JsonValue, name: str) -> bool:
        """Return one exact boolean field."""
        if not isinstance(value, bool):
            raise TypeError(f"{name} must be boolean")
        return value

    def text_tuple(
        self,
        value: JsonValue,
        name: str,
        maximum: int,
    ) -> tuple[str, ...]:
        """Return one bounded tuple reconstructed from a JSON array."""
        values = self.array(value, name, maximum)
        return tuple(
            self.text(item, f"{name}[{index}]")
            for index, item in enumerate(values)
        )

    def enum[EnumT: StrEnum](
        self,
        enum_type: type[EnumT],
        value: JsonValue,
        name: str,
    ) -> EnumT:
        """Return one closed string-enum field."""
        text = self.text(value, name)
        try:
            return enum_type(text)
        except ValueError as error:
            raise ValueError(f"{name} is unsupported: {text}") from error


REFERENCE_EVIDENCE_JSON_VALUE_READER = ReferenceEvidenceJsonValueReader(
    requirements=REFERENCE_EVIDENCE_VALUE_REQUIREMENTS
)
