"""JSON mapping for reference extraction evidence."""

from projectkoios.ingestion.json.value import JsonValue
from projectkoios.ingestion.models import IngestionStatus
from projectkoios.ingestion.reference.evidence.extraction import (
    ReferenceEvidenceExtraction,
)
from projectkoios.ingestion.reference.evidence.json.artifact import (
    ReferenceEvidenceArtifactJsonCodec,
)
from projectkoios.ingestion.reference.evidence.json.value import (
    REFERENCE_EVIDENCE_JSON_VALUE_READER,
)


class ReferenceEvidenceExtractionJsonCodec:
    """Project and reconstruct the exact extraction evidence object."""

    __slots__ = ()

    @staticmethod
    def to_json_value(
        extraction: ReferenceEvidenceExtraction,
    ) -> dict[str, JsonValue]:
        return {
            "artifact": ReferenceEvidenceArtifactJsonCodec.to_json_value(
                extraction.artifact
            ),
            "contract_version": extraction.contract_version,
            "manifest_id": extraction.manifest_id,
            "document_id": extraction.document_id,
            "status": extraction.status.value,
            "extractor_name": extraction.extractor_name,
            "extractor_version": extraction.extractor_version,
            "configuration_digest": extraction.configuration_digest,
            "warning_count": extraction.warning_count,
        }

    @staticmethod
    def from_json_value(value: JsonValue) -> ReferenceEvidenceExtraction:
        field = REFERENCE_EVIDENCE_JSON_VALUE_READER
        mapping = field.mapping(
            value,
            "extraction",
            {
                "artifact",
                "contract_version",
                "manifest_id",
                "document_id",
                "status",
                "extractor_name",
                "extractor_version",
                "configuration_digest",
                "warning_count",
            },
        )
        return ReferenceEvidenceExtraction(
            artifact=ReferenceEvidenceArtifactJsonCodec.from_json_value(
                mapping["artifact"],
                name="extraction.artifact",
            ),
            contract_version=field.text(
                mapping["contract_version"],
                "extraction.contract_version",
            ),
            manifest_id=field.text(
                mapping["manifest_id"],
                "extraction.manifest_id",
            ),
            document_id=field.text(
                mapping["document_id"],
                "extraction.document_id",
            ),
            status=field.enum(
                IngestionStatus,
                mapping["status"],
                "extraction.status",
            ),
            extractor_name=field.text(
                mapping["extractor_name"],
                "extraction.extractor_name",
            ),
            extractor_version=field.text(
                mapping["extractor_version"],
                "extraction.extractor_version",
            ),
            configuration_digest=field.text(
                mapping["configuration_digest"],
                "extraction.configuration_digest",
            ),
            warning_count=field.integer(
                mapping["warning_count"],
                "extraction.warning_count",
            ),
        )
