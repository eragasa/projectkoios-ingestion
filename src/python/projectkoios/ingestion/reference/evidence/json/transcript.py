"""JSON mapping for clean-transcript reference evidence."""

from projectkoios.ingestion.clean_transcript import CleanTranscriptStatus
from projectkoios.ingestion.json.value import JsonValue
from projectkoios.ingestion.reference.evidence.json.artifact import (
    ReferenceEvidenceArtifactJsonCodec,
)
from projectkoios.ingestion.reference.evidence.json.value import (
    REFERENCE_EVIDENCE_JSON_VALUE_READER,
)
from projectkoios.ingestion.reference.evidence.layout import (
    ReferenceEvidenceLayoutIdentityInventory,
)
from projectkoios.ingestion.reference.evidence.limits.definition import (
    REFERENCE_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.reference.evidence.transcript import (
    ReferenceEvidenceTranscript,
)


class ReferenceEvidenceTranscriptJsonCodec:
    """Project and reconstruct the exact transcript evidence object."""

    __slots__ = ()

    @staticmethod
    def to_json_value(
        transcript: ReferenceEvidenceTranscript,
    ) -> dict[str, JsonValue]:
        return {
            "artifact": ReferenceEvidenceArtifactJsonCodec.to_json_value(
                transcript.artifact
            ),
            "result_id": transcript.result_id,
            "status": transcript.status.value,
            "structured_transcription_result_id": (
                transcript.structured_transcription_result_id
            ),
            "layout_result_ids": list(transcript.layout_result_ids),
            "text_sha256": transcript.text_sha256,
            "text_utf8_byte_length": transcript.text_utf8_byte_length,
            "processor_name": transcript.processor_name,
            "processor_version": transcript.processor_version,
            "configuration_digest": transcript.configuration_digest,
            "warning_count": transcript.warning_count,
        }

    @staticmethod
    def from_json_value(value: JsonValue) -> ReferenceEvidenceTranscript:
        field = REFERENCE_EVIDENCE_JSON_VALUE_READER
        mapping = field.mapping(
            value,
            "transcript",
            {
                "artifact",
                "result_id",
                "status",
                "structured_transcription_result_id",
                "layout_result_ids",
                "text_sha256",
                "text_utf8_byte_length",
                "processor_name",
                "processor_version",
                "configuration_digest",
                "warning_count",
            },
        )
        return ReferenceEvidenceTranscript(
            artifact=ReferenceEvidenceArtifactJsonCodec.from_json_value(
                mapping["artifact"],
                name="transcript.artifact",
            ),
            result_id=field.text(
                mapping["result_id"],
                "transcript.result_id",
            ),
            status=field.enum(
                CleanTranscriptStatus,
                mapping["status"],
                "transcript.status",
            ),
            structured_transcription_result_id=field.text(
                mapping["structured_transcription_result_id"],
                "transcript.structured_transcription_result_id",
            ),
            layout_result_ids=ReferenceEvidenceLayoutIdentityInventory(
                *field.text_tuple(
                    mapping["layout_result_ids"],
                    "transcript.layout_result_ids",
                    REFERENCE_EVIDENCE_LIMITS.maximum_layout_identities,
                )
            ),
            text_sha256=field.text(
                mapping["text_sha256"],
                "transcript.text_sha256",
            ),
            text_utf8_byte_length=field.integer(
                mapping["text_utf8_byte_length"],
                "transcript.text_utf8_byte_length",
            ),
            processor_name=field.text(
                mapping["processor_name"],
                "transcript.processor_name",
            ),
            processor_version=field.text(
                mapping["processor_version"],
                "transcript.processor_version",
            ),
            configuration_digest=field.text(
                mapping["configuration_digest"],
                "transcript.configuration_digest",
            ),
            warning_count=field.integer(
                mapping["warning_count"],
                "transcript.warning_count",
            ),
        )
