"""JSON mapping for bound reference-evidence artifacts."""

from projectkoios.ingestion.json.value import JsonValue
from projectkoios.ingestion.reference.evidence.artifact import (
    ReferenceEvidenceArtifact,
)
from projectkoios.ingestion.reference.evidence.json.value import (
    REFERENCE_EVIDENCE_JSON_VALUE_READER,
)


class ReferenceEvidenceArtifactJsonCodec:
    """Project and reconstruct one exact artifact identity object."""

    __slots__ = ()

    @staticmethod
    def to_json_value(
        artifact: ReferenceEvidenceArtifact,
    ) -> dict[str, JsonValue]:
        return {
            "media_type": artifact.media_type,
            "sha256": artifact.sha256,
            "byte_length": artifact.byte_length,
        }

    @staticmethod
    def from_json_value(
        value: JsonValue,
        *,
        name: str,
    ) -> ReferenceEvidenceArtifact:
        field = REFERENCE_EVIDENCE_JSON_VALUE_READER
        mapping = field.mapping(
            value,
            name,
            {"media_type", "sha256", "byte_length"},
        )
        return ReferenceEvidenceArtifact(
            media_type=field.text(
                mapping["media_type"],
                f"{name}.media_type",
            ),
            sha256=field.text(mapping["sha256"], f"{name}.sha256"),
            byte_length=field.integer(
                mapping["byte_length"],
                f"{name}.byte_length",
            ),
        )
