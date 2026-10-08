"""Aggregate JSON mapping for reference-evidence records."""

from projectkoios.ingestion.json.value import JsonValue
from projectkoios.ingestion.reference.evidence.completeness import (
    ReferenceEvidenceCompletenessReasonInventory,
)
from projectkoios.ingestion.reference.evidence.json.audit import (
    ReferenceEvidenceAuditJsonCodec,
)
from projectkoios.ingestion.reference.evidence.json.extraction import (
    ReferenceEvidenceExtractionJsonCodec,
)
from projectkoios.ingestion.reference.evidence.json.source import (
    ReferenceEvidenceSourceJsonCodec,
)
from projectkoios.ingestion.reference.evidence.json.transcript import (
    ReferenceEvidenceTranscriptJsonCodec,
)
from projectkoios.ingestion.reference.evidence.json.value import (
    REFERENCE_EVIDENCE_JSON_VALUE_READER,
)
from projectkoios.ingestion.reference.evidence.limitation import (
    ReferenceEvidenceLimitationInventory,
)
from projectkoios.ingestion.reference.evidence.limits.definition import (
    REFERENCE_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.reference.evidence.record import (
    ReferenceEvidenceRecord,
)
from projectkoios.ingestion.reference.evidence.status import (
    ReferenceEvidenceCompleteness,
    ReferenceEvidenceContractStatus,
)


class ReferenceEvidenceRecordJsonCodec:
    """Project and reconstruct the exact aggregate wire object."""

    __slots__ = ()

    @staticmethod
    def to_json_value(record: ReferenceEvidenceRecord) -> JsonValue:
        if type(record) is not ReferenceEvidenceRecord:
            raise TypeError("value must be a ReferenceEvidenceRecord")
        return {
            "record_id": record.record_id,
            "contract_id": record.contract_id,
            "contract_version": record.contract_version,
            "contract_status": record.contract_status.value,
            "schema_version": record.schema_version,
            "media_type": record.media_type,
            "generator_name": record.generator_name,
            "generator_version": record.generator_version,
            "completeness": record.completeness.value,
            "completeness_reasons": list(record.completeness_reasons),
            "source": ReferenceEvidenceSourceJsonCodec.to_json_value(
                record.source
            ),
            "extraction": ReferenceEvidenceExtractionJsonCodec.to_json_value(
                record.extraction
            ),
            "transcript": ReferenceEvidenceTranscriptJsonCodec.to_json_value(
                record.transcript
            ),
            "derivation_audit": (
                ReferenceEvidenceAuditJsonCodec.to_json_value(
                    record.derivation_audit
                )
            ),
            "limitations": list(record.limitations),
        }

    @staticmethod
    def from_json_value(value: JsonValue) -> ReferenceEvidenceRecord:
        field = REFERENCE_EVIDENCE_JSON_VALUE_READER
        root = field.mapping(
            value,
            "reference evidence",
            {
                "record_id",
                "contract_id",
                "contract_version",
                "contract_status",
                "schema_version",
                "media_type",
                "generator_name",
                "generator_version",
                "completeness",
                "completeness_reasons",
                "source",
                "extraction",
                "transcript",
                "derivation_audit",
                "limitations",
            },
        )
        return ReferenceEvidenceRecord(
            record_id=field.text(root["record_id"], "record_id"),
            contract_id=field.text(root["contract_id"], "contract_id"),
            contract_version=field.text(
                root["contract_version"],
                "contract_version",
            ),
            contract_status=field.enum(
                ReferenceEvidenceContractStatus,
                root["contract_status"],
                "contract_status",
            ),
            schema_version=field.integer(
                root["schema_version"],
                "schema_version",
            ),
            media_type=field.text(root["media_type"], "media_type"),
            generator_name=field.text(
                root["generator_name"],
                "generator_name",
            ),
            generator_version=field.text(
                root["generator_version"],
                "generator_version",
            ),
            completeness=field.enum(
                ReferenceEvidenceCompleteness,
                root["completeness"],
                "completeness",
            ),
            completeness_reasons=(
                ReferenceEvidenceCompletenessReasonInventory(
                    *field.text_tuple(
                        root["completeness_reasons"],
                        "completeness_reasons",
                        REFERENCE_EVIDENCE_LIMITS.maximum_limitations,
                    )
                )
            ),
            source=ReferenceEvidenceSourceJsonCodec.from_json_value(
                root["source"]
            ),
            extraction=(
                ReferenceEvidenceExtractionJsonCodec.from_json_value(
                    root["extraction"]
                )
            ),
            transcript=ReferenceEvidenceTranscriptJsonCodec.from_json_value(
                root["transcript"]
            ),
            derivation_audit=(
                ReferenceEvidenceAuditJsonCodec.from_json_value(
                    root["derivation_audit"]
                )
            ),
            limitations=ReferenceEvidenceLimitationInventory(
                *field.text_tuple(
                    root["limitations"],
                    "limitations",
                    REFERENCE_EVIDENCE_LIMITS.maximum_limitations,
                )
            ),
        )
