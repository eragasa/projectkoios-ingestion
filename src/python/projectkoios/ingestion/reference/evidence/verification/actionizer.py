"""Deterministic consumer-side reference-evidence verification action."""

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.reference.evidence.error import (
    ReferenceEvidenceVerificationError,
)
from projectkoios.ingestion.reference.evidence.verification.artifact import (
    ReferenceEvidenceVerifiedArtifact,
    ReferenceEvidenceVerifiedArtifactInventory,
)
from projectkoios.ingestion.reference.evidence.verification.request import (
    ReferenceEvidenceVerificationRequest,
)
from projectkoios.ingestion.reference.evidence.verification.result import (
    ReferenceEvidenceVerificationResult,
)


class ReferenceEvidenceVerificationActionizer(
    DataObjectActionizer[
        ReferenceEvidenceVerificationRequest,
        ReferenceEvidenceVerificationResult,
    ]
):
    """Verify expected source identity and supplied exact producer artifacts."""

    __slots__ = ()

    def action(
        self,
        *,
        request: ReferenceEvidenceVerificationRequest,
    ) -> ReferenceEvidenceVerificationResult:
        """Return typed verification coverage or fail on any mismatch."""
        if type(request) is not ReferenceEvidenceVerificationRequest:
            raise TypeError(
                "request must be ReferenceEvidenceVerificationRequest"
            )
        record = request.record
        record.require_reusable()
        source = record.source
        if (
            source.content_sha256 != request.source_sha256
            or source.byte_length != request.source_byte_length
            or source.media_type != request.source_media_type
            or source.blob_id != f"blob:sha256:{request.source_sha256}"
        ):
            raise ReferenceEvidenceVerificationError(
                "reference evidence does not match the expected source bytes"
            )

        verified: list[ReferenceEvidenceVerifiedArtifact] = []
        optional_artifacts = (
            (
                "extraction artifact",
                record.extraction.artifact,
                request.extraction_artifact,
                ReferenceEvidenceVerifiedArtifact.EXTRACTION,
            ),
            (
                "serialized clean-transcript result",
                record.transcript.artifact,
                request.clean_transcript_result_bytes,
                ReferenceEvidenceVerifiedArtifact.CLEAN_TRANSCRIPT,
            ),
            (
                "derivation-audit artifact",
                record.derivation_audit.artifact,
                request.derivation_audit_artifact,
                ReferenceEvidenceVerifiedArtifact.DERIVATION_AUDIT,
            ),
        )
        for name, identity, content, kind in optional_artifacts:
            if content is not None:
                identity.verify(content, name=name)
                verified.append(kind)
        return ReferenceEvidenceVerificationResult(
            record=record,
            verified_artifacts=ReferenceEvidenceVerifiedArtifactInventory(
                *verified
            ),
        )
