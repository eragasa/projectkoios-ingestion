"""Immutable requests for reading-evidence source equivalence."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.storage.transcript.reading.evidence.equivalence.kind import (  # noqa: E501
    ReadingEvidenceEquivalenceKind,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.materialization.evidence import (  # noqa: E501
    ReadingEvidenceMaterializationEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.source.result import (
    ReadingEvidenceSourceResult,
)


@dataclass(frozen=True, slots=True)
class ReadingEvidenceEquivalenceRequest(DataObjectActionRequest):
    """Bind two independently verified canonical source results."""

    kind: ReadingEvidenceEquivalenceKind
    reference: ReadingEvidenceSourceResult
    observed: ReadingEvidenceSourceResult
    reference_materialization: ReadingEvidenceMaterializationEvidence | None
    replay_materialization: ReadingEvidenceMaterializationEvidence | None
    request_id: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ReadingEvidenceEquivalenceKind):
            raise TypeError("equivalence kind is invalid")
        if type(self.reference) is not ReadingEvidenceSourceResult:
            raise TypeError("reference source result is invalid")
        if type(self.observed) is not ReadingEvidenceSourceResult:
            raise TypeError("observed source result is invalid")
        if self.kind is ReadingEvidenceEquivalenceKind.SAME_STORE_REPLAY:
            if (
                type(self.reference_materialization)
                is not ReadingEvidenceMaterializationEvidence
                or type(self.replay_materialization)
                is not ReadingEvidenceMaterializationEvidence
            ):
                raise TypeError(
                    "same-store materialization evidence is required"
                )
        elif (
            self.reference_materialization is not None
            or self.replay_materialization is not None
        ):
            raise ValueError(
                "independent rebuild cannot bind materialization evidence"
            )
        object.__setattr__(
            self,
            "request_id",
            stable_id(
                "reading-evidence-equivalence-request",
                self.kind.value,
                self.reference.result_id,
                self.observed.result_id,
                (
                    self.reference_materialization.evidence_id
                    if self.reference_materialization is not None
                    else None
                ),
                (
                    self.replay_materialization.evidence_id
                    if self.replay_materialization is not None
                    else None
                ),
            ),
        )
