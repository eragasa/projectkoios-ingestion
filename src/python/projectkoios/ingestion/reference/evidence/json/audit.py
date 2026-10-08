"""JSON mapping for recorded producer-audit evidence."""

from projectkoios.ingestion.json.value import JsonValue
from projectkoios.ingestion.provenance.audit import DerivationAuditStatus
from projectkoios.ingestion.reference.evidence.audit import (
    ReferenceEvidenceAudit,
    ReferenceEvidenceAuditScope,
)
from projectkoios.ingestion.reference.evidence.json.artifact import (
    ReferenceEvidenceArtifactJsonCodec,
)
from projectkoios.ingestion.reference.evidence.json.layer import (
    REFERENCE_EVIDENCE_LAYER_COUNT_JSON_CODEC,
)
from projectkoios.ingestion.reference.evidence.json.value import (
    REFERENCE_EVIDENCE_JSON_VALUE_READER,
)
from projectkoios.ingestion.reference.evidence.layer import (
    ReferenceEvidenceLayerCountInventory,
)
from projectkoios.ingestion.reference.evidence.limits.definition import (
    REFERENCE_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.reference.evidence.lineage import (
    ReferenceEvidenceAuditArtifactIdentityInventory,
)


class ReferenceEvidenceAuditJsonCodec:
    """Project and reconstruct exact recorded audit evidence."""

    __slots__ = ()

    @staticmethod
    def to_json_value(
        audit: ReferenceEvidenceAudit,
    ) -> dict[str, JsonValue]:
        return {
            "artifact": ReferenceEvidenceArtifactJsonCodec.to_json_value(
                audit.artifact
            ),
            "contract_version": audit.contract_version,
            "report_id": audit.report_id,
            "status": audit.status.value,
            "scope": audit.scope.value,
            "independently_revalidated": audit.independently_revalidated,
            "processor_name": audit.processor_name,
            "processor_version": audit.processor_version,
            "audited_artifact_ids": list(audit.audited_artifact_ids),
            "audited_layer_counts": [
                REFERENCE_EVIDENCE_LAYER_COUNT_JSON_CODEC.to_json_value(item)
                for item in audit.audited_layer_counts
            ],
            "finding_count": audit.finding_count,
        }

    @staticmethod
    def from_json_value(value: JsonValue) -> ReferenceEvidenceAudit:
        field = REFERENCE_EVIDENCE_JSON_VALUE_READER
        mapping = field.mapping(
            value,
            "derivation_audit",
            {
                "artifact",
                "contract_version",
                "report_id",
                "status",
                "scope",
                "independently_revalidated",
                "processor_name",
                "processor_version",
                "audited_artifact_ids",
                "audited_layer_counts",
                "finding_count",
            },
        )
        return ReferenceEvidenceAudit(
            artifact=ReferenceEvidenceArtifactJsonCodec.from_json_value(
                mapping["artifact"],
                name="derivation_audit.artifact",
            ),
            contract_version=field.text(
                mapping["contract_version"],
                "derivation_audit.contract_version",
            ),
            report_id=field.text(
                mapping["report_id"],
                "derivation_audit.report_id",
            ),
            status=field.enum(
                DerivationAuditStatus,
                mapping["status"],
                "derivation_audit.status",
            ),
            scope=field.enum(
                ReferenceEvidenceAuditScope,
                mapping["scope"],
                "derivation_audit.scope",
            ),
            independently_revalidated=field.boolean(
                mapping["independently_revalidated"],
                "derivation_audit.independently_revalidated",
            ),
            processor_name=field.text(
                mapping["processor_name"],
                "derivation_audit.processor_name",
            ),
            processor_version=field.text(
                mapping["processor_version"],
                "derivation_audit.processor_version",
            ),
            audited_artifact_ids=(
                ReferenceEvidenceAuditArtifactIdentityInventory(
                    *field.text_tuple(
                        mapping["audited_artifact_ids"],
                        "derivation_audit.audited_artifact_ids",
                        REFERENCE_EVIDENCE_LIMITS.maximum_lineage_identities,
                    )
                )
            ),
            audited_layer_counts=ReferenceEvidenceLayerCountInventory(
                *(
                    REFERENCE_EVIDENCE_LAYER_COUNT_JSON_CODEC.from_json_value(
                        item,
                        index=index,
                    )
                    for index, item in enumerate(
                        field.array(
                            mapping["audited_layer_counts"],
                            "derivation_audit.audited_layer_counts",
                            REFERENCE_EVIDENCE_LIMITS.maximum_layer_counts,
                        )
                    )
                )
            ),
            finding_count=field.integer(
                mapping["finding_count"],
                "derivation_audit.finding_count",
            ),
        )
