"""Immutable Docling reading-order candidate results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.actionizer.result import (
    AbstractDataObjectActionResult,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.reading.order.candidate import (
    LayoutReadingOrderCandidateEvidence,
)
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation

from .kind import DoclingReadingOrderFailureKind, DoclingReadingOrderStatus
from .request import DoclingReadingOrderRequest


@dataclass(frozen=True, slots=True)
class DoclingReadingOrderResult(AbstractDataObjectActionResult):
    """Record complete candidate evidence or one unresolved outcome."""

    ACTIONIZER_NAME: ClassVar[str] = (
        "docling-reading-order-candidate-actionizer"
    )
    ACTIONIZER_VERSION: ClassVar[str] = "1"

    request: DoclingReadingOrderRequest
    provider_implementation_id: str
    status: DoclingReadingOrderStatus
    candidate_evidence: LayoutReadingOrderCandidateEvidence | None
    failure_kind: DoclingReadingOrderFailureKind | None
    result_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.request) is not DoclingReadingOrderRequest:
            raise TypeError("request must be DoclingReadingOrderRequest")
        provider = LayoutValueValidation.require_text(
            "provider_implementation_id", self.provider_implementation_id
        )
        if not isinstance(self.status, DoclingReadingOrderStatus):
            raise TypeError("status must be DoclingReadingOrderStatus")
        if self.status is DoclingReadingOrderStatus.CANDIDATE_PRODUCED:
            if (
                provider
                != self.request.configuration.provider_implementation_id
            ):
                raise ValueError(
                    "successful provider identity differs from configuration"
                )
            if (
                type(self.candidate_evidence)
                is not LayoutReadingOrderCandidateEvidence
            ):
                raise ValueError(
                    "candidate status requires exact candidate evidence"
                )
            if self.failure_kind is not None:
                raise ValueError(
                    "candidate status cannot carry failure evidence"
                )
            evidence = self.candidate_evidence
            if (
                evidence.source_request_id != self.request.request_id
                or evidence.producer_implementation_id != provider
                or evidence.render_id != self.request.render_id
                or evidence.upstream_evidence_id
                != self.request.upstream_evidence_id
                or evidence.direction is not self.request.direction
                or evidence.elements != self.request.elements
            ):
                raise ValueError(
                    "candidate evidence differs from the exact Docling request"
                )
            expected_ids = tuple(
                element.region_id for element in self.request.elements
            )
            actual_ids = tuple(evidence.candidate)
            if len(actual_ids) != len(expected_ids) or set(actual_ids) != set(
                expected_ids
            ):
                raise ValueError(
                    "candidate must be an exact request element permutation"
                )
        else:
            if self.candidate_evidence is not None:
                raise ValueError(
                    "unresolved result cannot carry candidate evidence"
                )
            if not isinstance(
                self.failure_kind, DoclingReadingOrderFailureKind
            ):
                raise ValueError("unresolved result requires failure evidence")
            if (
                provider
                != self.request.configuration.provider_implementation_id
                and self.failure_kind
                is not DoclingReadingOrderFailureKind.PROVIDER_VERSION_MISMATCH
            ):
                raise ValueError(
                    "mismatching provider requires version-mismatch evidence"
                )
        object.__setattr__(self, "provider_implementation_id", provider)
        object.__setattr__(
            self,
            "result_id",
            stable_id(
                "docling-reading-order-result",
                self.request.request_id,
                provider,
                self.status,
                (
                    None
                    if self.candidate_evidence is None
                    else self.candidate_evidence.evidence_id
                ),
                self.failure_kind,
                self.ACTIONIZER_NAME,
                self.ACTIONIZER_VERSION,
            ),
        )

    @property
    def requires_verification(self) -> bool:
        """Make explicit that provider completion never resolves order."""
        return self.status is DoclingReadingOrderStatus.CANDIDATE_PRODUCED
