"""Deterministic local-detector admission-gate results."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.base.actionizer.result import (
    AbstractDataObjectActionResult,
)
from projectkoios.ingestion.identity import stable_id

from ..limitation import CocoLayoutDetectorLimitationCode
from .reason import CocoLayoutDetectorGateReason, CocoLayoutDetectorGateStatus
from .request import CocoLayoutDetectorGateRequest


@dataclass(frozen=True, slots=True)
class CocoLayoutDetectorGateResult(AbstractDataObjectActionResult):
    """Admit only evidence eligible for deterministic layout finalization."""

    request: CocoLayoutDetectorGateRequest
    status: CocoLayoutDetectorGateStatus
    reasons: tuple[CocoLayoutDetectorGateReason, ...]
    result_id: str = field(init=False)

    @classmethod
    def create(
        cls, *, request: CocoLayoutDetectorGateRequest
    ) -> CocoLayoutDetectorGateResult:
        """Derive the only gate outcome for one exact evidence chain."""
        status, reasons = cls.derive(request)
        return cls(request=request, status=status, reasons=reasons)

    @staticmethod
    def derive(
        request: CocoLayoutDetectorGateRequest,
    ) -> tuple[
        CocoLayoutDetectorGateStatus,
        tuple[CocoLayoutDetectorGateReason, ...],
    ]:
        """Derive status and reasons without constructing a result."""
        if type(request) is not CocoLayoutDetectorGateRequest:
            raise TypeError("request must be CocoLayoutDetectorGateRequest")
        reasons: set[CocoLayoutDetectorGateReason] = set()
        if request.review_case.requires_review:
            reasons.add(
                CocoLayoutDetectorGateReason.DETERMINISTIC_LAYOUT_REVIEW_REQUIRED
            )
        if (
            len(request.detector_result.adaptations)
            < request.configuration.minimum_accepted_detections
        ):
            reasons.add(
                CocoLayoutDetectorGateReason.INSUFFICIENT_ACCEPTED_DETECTIONS
            )
        if (
            len(request.detector_result.limitations)
            > request.configuration.maximum_limitations
        ):
            reasons.add(CocoLayoutDetectorGateReason.LIMITATION_BOUND_EXCEEDED)
        if request.configuration.unsupported_labels_require_escalation and any(
            limitation.code
            is CocoLayoutDetectorLimitationCode.UNSUPPORTED_LABEL
            for limitation in request.detector_result.limitations
        ):
            reasons.add(CocoLayoutDetectorGateReason.UNSUPPORTED_LABEL_OBSERVED)
        ordered = tuple(sorted(reasons, key=str))
        status = (
            CocoLayoutDetectorGateStatus.ESCALATION_REQUIRED
            if ordered
            else CocoLayoutDetectorGateStatus.ADMITTED
        )
        return status, ordered

    def __post_init__(self) -> None:
        if type(self.request) is not CocoLayoutDetectorGateRequest:
            raise TypeError("request must be CocoLayoutDetectorGateRequest")
        if not isinstance(self.status, CocoLayoutDetectorGateStatus):
            raise TypeError("status must be CocoLayoutDetectorGateStatus")
        if not isinstance(self.reasons, tuple) or any(
            not isinstance(reason, CocoLayoutDetectorGateReason)
            for reason in self.reasons
        ):
            raise TypeError("reasons must contain gate reasons")
        if self.reasons != tuple(sorted(set(self.reasons), key=str)):
            raise ValueError("gate reasons must be unique and sorted")
        expected_status, expected_reasons = self.derive(self.request)
        if (
            self.status is not expected_status
            or self.reasons != expected_reasons
        ):
            raise ValueError("gate result differs from deterministic evidence")
        object.__setattr__(
            self,
            "result_id",
            stable_id(
                "coco-layout-detector-gate-result",
                self.request.request_id,
                self.status,
                self.reasons,
            ),
        )

    @property
    def admitted_for_deterministic_finalization(self) -> bool:
        """Return finalization eligibility without granting publication."""
        return self.status is CocoLayoutDetectorGateStatus.ADMITTED
