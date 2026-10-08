"""Producer lineage verification before reference-evidence projection."""

from dataclasses import dataclass

from projectkoios.ingestion.clean_transcript import CleanTranscriptStatus
from projectkoios.ingestion.models import IngestionStatus
from projectkoios.ingestion.provenance.audit import DerivationAuditStatus
from projectkoios.ingestion.reference.evidence.error import (
    ReferenceEvidenceVerificationError,
)
from projectkoios.ingestion.reference.evidence.layer import (
    ReferenceEvidenceLayerCount,
    ReferenceEvidenceLayerCountInventory,
)
from projectkoios.ingestion.reference.evidence.projection.request import (
    ReferenceEvidenceProjectionRequest,
)


@dataclass(frozen=True, slots=True)
class ReferenceEvidenceProjectionLineageVerifier:
    """Bind one request and validate producer statuses and source lineage."""

    request: ReferenceEvidenceProjectionRequest

    def __post_init__(self) -> None:
        if type(self.request) is not ReferenceEvidenceProjectionRequest:
            raise TypeError(
                "request must be ReferenceEvidenceProjectionRequest"
            )

    def verified_layer_counts(self) -> ReferenceEvidenceLayerCountInventory:
        """Validate lineage and return its typed audited-layer inventory."""
        request = self.request
        extraction_result = request.extraction_result
        clean_transcript = request.clean_transcript
        derivation_audit = request.derivation_audit
        document = extraction_result.document
        source = document.source
        manifest = extraction_result.manifest
        if manifest.status is not IngestionStatus.COMPLETED:
            raise ReferenceEvidenceVerificationError(
                "incomplete extraction cannot produce complete "
                "reference evidence"
            )
        if (
            clean_transcript.status
            is not CleanTranscriptStatus.AUTOMATED_UNREVIEWED
        ):
            raise ReferenceEvidenceVerificationError(
                "unsupported clean-transcript status"
            )
        if (
            clean_transcript.document_id != document.document_id
            or clean_transcript.source_id != source.source_id
            or clean_transcript.source_blob_id != source.blob_id
            or clean_transcript.source_content_hash != source.content_hash
        ):
            raise ReferenceEvidenceVerificationError(
                "clean transcript does not match extraction source bytes"
            )
        if (
            derivation_audit.source_id != source.source_id
            or derivation_audit.source_blob_id != source.blob_id
            or derivation_audit.source_content_hash != source.content_hash
            or derivation_audit.document_id != document.document_id
        ):
            raise ReferenceEvidenceVerificationError(
                "derivation audit does not match extraction source bytes"
            )
        if derivation_audit.status is not DerivationAuditStatus.PASSED:
            raise ReferenceEvidenceVerificationError(
                "failed derivation audit cannot produce complete "
                "reference evidence"
            )
        if derivation_audit.findings:
            raise ReferenceEvidenceVerificationError(
                "passing derivation audit contains contradictory findings"
            )
        try:
            return ReferenceEvidenceLayerCountInventory(
                *(
                    ReferenceEvidenceLayerCount(layer=name, count=int(count))
                    for name, count in derivation_audit.audited_layer_counts
                )
            )
        except (TypeError, ValueError) as error:
            raise ReferenceEvidenceVerificationError(
                "derivation audit layer counts are malformed"
            ) from error
