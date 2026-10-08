"""JSON mapping for reference source-byte identity."""

from projectkoios.ingestion.json.value import JsonValue
from projectkoios.ingestion.reference.evidence.json.value import (
    REFERENCE_EVIDENCE_JSON_VALUE_READER,
)
from projectkoios.ingestion.reference.evidence.source import (
    ReferenceEvidenceSource,
)


class ReferenceEvidenceSourceJsonCodec:
    """Project and reconstruct one exact source identity object."""

    __slots__ = ()

    @staticmethod
    def to_json_value(
        source: ReferenceEvidenceSource,
    ) -> dict[str, JsonValue]:
        return {
            "blob_id": source.blob_id,
            "hash_algorithm": source.hash_algorithm,
            "content_sha256": source.content_sha256,
            "byte_length": source.byte_length,
            "media_type": source.media_type,
        }

    @staticmethod
    def from_json_value(value: JsonValue) -> ReferenceEvidenceSource:
        field = REFERENCE_EVIDENCE_JSON_VALUE_READER
        mapping = field.mapping(
            value,
            "source",
            {
                "blob_id",
                "hash_algorithm",
                "content_sha256",
                "byte_length",
                "media_type",
            },
        )
        return ReferenceEvidenceSource(
            blob_id=field.text(mapping["blob_id"], "source.blob_id"),
            hash_algorithm=field.text(
                mapping["hash_algorithm"],
                "source.hash_algorithm",
            ),
            content_sha256=field.text(
                mapping["content_sha256"],
                "source.content_sha256",
            ),
            byte_length=field.integer(
                mapping["byte_length"],
                "source.byte_length",
            ),
            media_type=field.text(
                mapping["media_type"],
                "source.media_type",
            ),
        )
