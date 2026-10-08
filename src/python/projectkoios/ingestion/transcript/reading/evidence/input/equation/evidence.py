"""Exact equation producer evidence."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.transcript.reading.evidence.equation.disposition import (  # noqa: E501
    ReadingEquationSelectionDisposition,
)
from projectkoios.ingestion.transcript.reading.evidence.equation.gate import (
    ReadingEquationGate,
)
from projectkoios.ingestion.transcript.reading.evidence.equation.status import (
    ReadingEquationRecognitionStatus,
)
from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.derivation import (  # noqa: E501
    ReadingEvidenceIdentityDerivation,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.input.producer.lineage import (  # noqa: E501
    ReadingProducerLineage,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.error import (
    ReadingEvidenceLimitError,
)


@dataclass(frozen=True, slots=True)
class ReadingEquationProducerEvidence:
    """Bind one equation assembly to source, recognition, and gate evidence."""

    assembly_id: ReadingEvidenceIdentity
    candidate_id: ReadingEvidenceIdentity
    lineage: ReadingProducerLineage
    native_representation: str | None
    recognized_representation: str | None
    selection_disposition: ReadingEquationSelectionDisposition
    recognition_status: ReadingEquationRecognitionStatus
    gate: ReadingEquationGate
    record_id: ReadingEvidenceIdentity = field(init=False)

    def __post_init__(self) -> None:
        roles = (
            (
                self.assembly_id,
                ReadingEvidenceIdentityKind.ASSEMBLY,
                "assembly_id",
            ),
            (
                self.candidate_id,
                ReadingEvidenceIdentityKind.CANDIDATE,
                "candidate_id",
            ),
        )
        for value, kind, name in roles:
            if (
                type(value) is not ReadingEvidenceIdentity
                or value.kind is not kind
            ):
                raise TypeError(f"{name} has the wrong identity role")
        if type(self.lineage) is not ReadingProducerLineage:
            raise TypeError("lineage must be ReadingProducerLineage")
        native = READING_EVIDENCE_LIMITS.require_optional_text(
            self.native_representation,
            "native_representation",
            maximum_bytes=READING_EVIDENCE_LIMITS.maximum_block_text_bytes,
        )
        recognized = READING_EVIDENCE_LIMITS.require_optional_text(
            self.recognized_representation,
            "recognized_representation",
            maximum_bytes=READING_EVIDENCE_LIMITS.maximum_block_text_bytes,
        )
        if native is None and recognized is None:
            raise ReadingEvidenceError(
                "equation requires at least one representation"
            )
        text_bytes = sum(
            len(label.encode()) for label in self.lineage.source_labels
        ) + sum(
            len(value.encode())
            for value in (native, recognized)
            if value is not None
        )
        if text_bytes > READING_EVIDENCE_LIMITS.maximum_single_record_bytes:
            raise ReadingEvidenceLimitError(
                "equation producer text exceeds its record limit"
            )
        if not isinstance(
            self.selection_disposition, ReadingEquationSelectionDisposition
        ):
            raise TypeError("selection_disposition has an unsupported type")
        if not isinstance(
            self.recognition_status, ReadingEquationRecognitionStatus
        ):
            raise TypeError(
                "recognition_status must be ReadingEquationRecognitionStatus"
            )
        if (
            self.recognition_status
            is ReadingEquationRecognitionStatus.SUCCEEDED
        ) is (recognized is None):
            raise ReadingEvidenceError(
                "recognition status conflicts with recognized representation"
            )
        if type(self.gate) is not ReadingEquationGate:
            raise TypeError("gate must be ReadingEquationGate")
        if self.gate.chunk_text_eligible and (
            self.selection_disposition
            is not ReadingEquationSelectionDisposition.PRIMARY
        ):
            raise ReadingEvidenceError(
                "only primary equation evidence can enter chunk text"
            )
        object.__setattr__(
            self,
            "record_id",
            ReadingEvidenceIdentityDerivation.derive(
                kind=ReadingEvidenceIdentityKind.EQUATION,
                prefix="reading-equation-producer",
                material={
                    "assembly_id": self.assembly_id.value,
                    "candidate_id": self.candidate_id.value,
                    "lineage": self.lineage.identity_material(),
                    "native_representation": native,
                    "recognized_representation": recognized,
                    "selection_disposition": self.selection_disposition,
                    "recognition_status": self.recognition_status,
                    "gate": self.gate,
                },
            ),
        )
