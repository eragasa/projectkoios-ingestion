"""Reversible bounded JSON contract for reference evidence."""

from typing import ClassVar

from projectkoios.ingestion.json.contract import JsonContract
from projectkoios.ingestion.json.error import (
    JsonDuplicateFieldError,
    JsonParseError,
    JsonSerializationError,
)
from projectkoios.ingestion.json.limits.definition import JsonLimits
from projectkoios.ingestion.json.limits.error import (
    JsonDocumentByteLimitError,
    JsonLimitError,
)
from projectkoios.ingestion.json.parser import JsonParser
from projectkoios.ingestion.json.serializer import JsonSerializer
from projectkoios.ingestion.json.value import JsonValue
from projectkoios.ingestion.reference.evidence.error import (
    ReferenceEvidenceError,
    ReferenceEvidenceParseError,
)
from projectkoios.ingestion.reference.evidence.json.record import (
    ReferenceEvidenceRecordJsonCodec,
)
from projectkoios.ingestion.reference.evidence.limits.definition import (
    REFERENCE_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.reference.evidence.limits.error import (
    ReferenceEvidenceLimitError,
)
from projectkoios.ingestion.reference.evidence.record import (
    ReferenceEvidenceRecord,
)


class ReferenceEvidenceJsonContract(JsonContract[ReferenceEvidenceRecord]):
    """Reconstruct and serialize schema-generation-1 reference evidence."""

    __slots__ = ()

    limits: ClassVar[JsonLimits] = JsonLimits(
        maximum_utf8_bytes=REFERENCE_EVIDENCE_LIMITS.maximum_document_bytes,
        maximum_container_depth=REFERENCE_EVIDENCE_LIMITS.maximum_json_container_depth,
        maximum_items=REFERENCE_EVIDENCE_LIMITS.maximum_json_items,
        maximum_string_bytes=REFERENCE_EVIDENCE_LIMITS.maximum_json_string_bytes,
        maximum_total_string_bytes=(
            REFERENCE_EVIDENCE_LIMITS.maximum_json_total_string_bytes
        ),
        maximum_number_characters=(
            REFERENCE_EVIDENCE_LIMITS.maximum_json_number_characters
        ),
    )
    parser_instance: ClassVar[JsonParser] = JsonParser(limits)
    serializer_instance: ClassVar[JsonSerializer] = JsonSerializer.canonical(
        limits=limits
    )

    @property
    def parser(self) -> JsonParser:
        return self.parser_instance

    @property
    def serializer(self) -> JsonSerializer:
        return self.serializer_instance

    @property
    def requires_canonical_replay(self) -> bool:
        return True

    def to_json_value(self, value: ReferenceEvidenceRecord) -> JsonValue:
        return ReferenceEvidenceRecordJsonCodec.to_json_value(value)

    def from_json_value(self, value: JsonValue) -> ReferenceEvidenceRecord:
        try:
            return ReferenceEvidenceRecordJsonCodec.from_json_value(value)
        except ReferenceEvidenceError:
            raise
        except (KeyError, TypeError, ValueError, RecursionError) as error:
            raise ReferenceEvidenceParseError(
                f"reference evidence is invalid: {error}"
            ) from error

    def serialize_text(self, value: ReferenceEvidenceRecord) -> str:
        try:
            return super().serialize_text(value)
        except JsonDocumentByteLimitError as error:
            raise ReferenceEvidenceLimitError(
                "reference-evidence serialization exceeds size limit"
            ) from error
        except JsonLimitError as error:
            raise ReferenceEvidenceLimitError(str(error)) from error
        except JsonSerializationError as error:
            raise ReferenceEvidenceError(
                "reference evidence cannot be canonically serialized"
            ) from error

    def serialize_bytes(self, value: ReferenceEvidenceRecord) -> bytes:
        try:
            return super().serialize_bytes(value)
        except JsonDocumentByteLimitError as error:
            raise ReferenceEvidenceLimitError(
                "reference-evidence serialization exceeds size limit"
            ) from error
        except JsonLimitError as error:
            raise ReferenceEvidenceLimitError(str(error)) from error
        except JsonSerializationError as error:
            raise ReferenceEvidenceError(
                "reference evidence cannot be canonically serialized"
            ) from error

    def parse_text(self, content: str) -> ReferenceEvidenceRecord:
        try:
            parsed = self.parser.parse_text(content)
        except JsonDocumentByteLimitError as error:
            raise ReferenceEvidenceLimitError(
                "reference evidence exceeds size limit"
            ) from error
        except JsonLimitError as error:
            raise ReferenceEvidenceLimitError(str(error)) from error
        except JsonDuplicateFieldError as error:
            raise ReferenceEvidenceParseError(
                "reference evidence is malformed JSON: "
                "duplicate JSON object field"
            ) from error
        except JsonParseError as error:
            raise ReferenceEvidenceParseError(
                f"reference evidence is malformed JSON: {error}"
            ) from error
        record = self.from_json_value(parsed)
        if self.serialize_text(record) != content:
            raise ReferenceEvidenceParseError(
                "reference evidence is not canonical serialization"
            )
        record.require_reusable()
        return record

    def parse_bytes(self, content: bytes) -> ReferenceEvidenceRecord:
        try:
            parsed = self.parser.parse_bytes(content)
        except JsonDocumentByteLimitError as error:
            raise ReferenceEvidenceLimitError(
                "reference evidence exceeds size limit"
            ) from error
        except JsonLimitError as error:
            raise ReferenceEvidenceLimitError(str(error)) from error
        except JsonDuplicateFieldError as error:
            raise ReferenceEvidenceParseError(
                "reference evidence is malformed JSON: "
                "duplicate JSON object field"
            ) from error
        except JsonParseError as error:
            raise ReferenceEvidenceParseError(
                f"reference evidence is malformed JSON: {error}"
            ) from error
        record = self.from_json_value(parsed)
        if self.serialize_bytes(record) != content:
            raise ReferenceEvidenceParseError(
                "reference evidence is not canonical serialization"
            )
        record.require_reusable()
        return record
