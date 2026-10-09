"""Deterministic generic per-category COCO region-admission result."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.base.actionizer.result import (
    AbstractDataObjectActionResult,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.adaptation import (
    CocoLayoutProposalAdaptation,
)
from projectkoios.ingestion.integrations.coco.layout.detector.limitation import (  # noqa: E501
    CocoLayoutDetectorLimitationInventory,
)
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation

from .evidence import (
    CocoLayoutRegionAdmissionDisposition,
    CocoLayoutRegionAdmissionEvidence,
    CocoLayoutRegionAdmissionEvidenceInventory,
)
from .outcome import (
    CocoLayoutCategoryAdmission,
    CocoLayoutCategoryAdmissionInventory,
    CocoLayoutCategoryAdmissionStatus,
)
from .overlap import coco_layout_intersection_over_union
from .request import CocoLayoutRegionAdmissionRequest


@dataclass(frozen=True, slots=True)
class CocoLayoutRegionAdmissionResult(AbstractDataObjectActionResult):
    """Expose independent category outcomes and all detector limitations."""

    request: CocoLayoutRegionAdmissionRequest
    category_outcomes: CocoLayoutCategoryAdmissionInventory
    limitations: CocoLayoutDetectorLimitationInventory
    actionizer_name: str
    actionizer_version: str
    result_id: str = field(init=False)

    @classmethod
    def create(
        cls,
        *,
        request: CocoLayoutRegionAdmissionRequest,
        actionizer_name: str,
        actionizer_version: str,
    ) -> CocoLayoutRegionAdmissionResult:
        """Derive all category outcomes from exact detector evidence."""
        outcomes, limitations = cls.derive(request)
        return cls(
            request=request,
            category_outcomes=outcomes,
            limitations=limitations,
            actionizer_name=actionizer_name,
            actionizer_version=actionizer_version,
        )

    @staticmethod
    def derive(
        request: CocoLayoutRegionAdmissionRequest,
    ) -> tuple[
        CocoLayoutCategoryAdmissionInventory,
        CocoLayoutDetectorLimitationInventory,
    ]:
        """Classify accepted adaptations independently by profile category."""
        if type(request) is not CocoLayoutRegionAdmissionRequest:
            raise TypeError("request must be a region admission request")
        configuration = request.configuration
        proposal_adaptations = tuple(request.proposal_result.adaptations)
        outcomes: list[CocoLayoutCategoryAdmission] = []
        for category in configuration.profile.categories:
            category_adaptations = tuple(
                adaptation
                for adaptation in proposal_adaptations
                if adaptation.detection.category_id == category.category_id
            )
            evidence = CocoLayoutRegionAdmissionResult.derive_category_evidence(
                request=request,
                adaptations=category_adaptations,
            )
            dispositions = tuple(item.disposition for item in evidence)
            if (
                CocoLayoutRegionAdmissionDisposition.ESCALATION_REQUIRED_LIMIT
                in dispositions
            ):
                status = CocoLayoutCategoryAdmissionStatus.ESCALATION_REQUIRED
            elif CocoLayoutRegionAdmissionDisposition.ADMITTED in dispositions:
                status = CocoLayoutCategoryAdmissionStatus.ADMITTED
            else:
                status = CocoLayoutCategoryAdmissionStatus.EMPTY
            outcomes.append(
                CocoLayoutCategoryAdmission(
                    category=category,
                    status=status,
                    evidence=evidence,
                )
            )
        return (
            CocoLayoutCategoryAdmissionInventory(*outcomes),
            request.detector_result.limitations,
        )

    @staticmethod
    def derive_category_evidence(
        *,
        request: CocoLayoutRegionAdmissionRequest,
        adaptations: tuple[CocoLayoutProposalAdaptation, ...],
    ) -> CocoLayoutRegionAdmissionEvidenceInventory:
        """Apply confidence, same-category deduplication, and count bounds."""
        configuration = request.configuration
        evidence: list[CocoLayoutRegionAdmissionEvidence] = []
        qualified: list[CocoLayoutProposalAdaptation] = []
        for adaptation in adaptations:
            if (
                adaptation.proposal.confidence
                < configuration.minimum_confidence
            ):
                evidence.append(
                    CocoLayoutRegionAdmissionEvidence(
                        admission_request_id=request.request_id,
                        adaptation=adaptation,
                        disposition=(
                            CocoLayoutRegionAdmissionDisposition.EXCLUDED_BELOW_CONFIDENCE
                        ),
                        selected_adaptation_id=None,
                    )
                )
            else:
                qualified.append(adaptation)
        qualified.sort(
            key=lambda value: (
                -value.proposal.confidence,
                value.proposal.proposal_id,
            )
        )
        selected: list[CocoLayoutProposalAdaptation] = []
        duplicate_evidence: list[CocoLayoutRegionAdmissionEvidence] = []
        for adaptation in qualified:
            retained = next(
                (
                    candidate
                    for candidate in selected
                    if coco_layout_intersection_over_union(
                        candidate.proposal.bounding_box_pixels,
                        adaptation.proposal.bounding_box_pixels,
                    )
                    >= configuration.duplicate_iou_threshold
                ),
                None,
            )
            if retained is None:
                selected.append(adaptation)
            else:
                duplicate_evidence.append(
                    CocoLayoutRegionAdmissionEvidence(
                        admission_request_id=request.request_id,
                        adaptation=adaptation,
                        disposition=(
                            CocoLayoutRegionAdmissionDisposition.EXCLUDED_DUPLICATE
                        ),
                        selected_adaptation_id=retained.adaptation_id,
                    )
                )
        evidence.extend(duplicate_evidence)
        selected_disposition = (
            CocoLayoutRegionAdmissionDisposition.ADMITTED
            if len(selected) <= configuration.maximum_regions_per_category
            else CocoLayoutRegionAdmissionDisposition.ESCALATION_REQUIRED_LIMIT
        )
        evidence.extend(
            CocoLayoutRegionAdmissionEvidence(
                admission_request_id=request.request_id,
                adaptation=adaptation,
                disposition=selected_disposition,
                selected_adaptation_id=None,
            )
            for adaptation in selected
        )
        evidence.sort(key=lambda item: item.adaptation.detection.annotation_id)
        return CocoLayoutRegionAdmissionEvidenceInventory(*evidence)

    def __post_init__(self) -> None:
        if type(self.request) is not CocoLayoutRegionAdmissionRequest:
            raise TypeError("request must be a region admission request")
        if type(self.category_outcomes) is not (
            CocoLayoutCategoryAdmissionInventory
        ):
            raise TypeError("category_outcomes must be an outcome inventory")
        if type(self.limitations) is not CocoLayoutDetectorLimitationInventory:
            raise TypeError("limitations must be a limitation inventory")
        actionizer_name = LayoutValueValidation.require_text(
            "actionizer_name", self.actionizer_name
        )
        actionizer_version = LayoutValueValidation.require_text(
            "actionizer_version", self.actionizer_version
        )
        expected_outcomes, expected_limitations = self.derive(self.request)
        if (
            self.category_outcomes != expected_outcomes
            or self.limitations != expected_limitations
        ):
            raise ValueError(
                "region admission differs from deterministic request derivation"
            )
        evidence_count = sum(
            len(outcome.evidence) for outcome in self.category_outcomes
        )
        observation_count = len(
            self.request.detector_result.request.observations
        )
        if evidence_count + len(self.limitations) != observation_count:
            raise ValueError(
                "region admission does not cover every observation"
            )
        object.__setattr__(self, "actionizer_name", actionizer_name)
        object.__setattr__(self, "actionizer_version", actionizer_version)
        object.__setattr__(
            self,
            "result_id",
            stable_id(
                "coco-layout-region-admission-result",
                self.request.request_id,
                self.category_outcomes.inventory_id,
                self.limitations.inventory_id,
                actionizer_name,
                actionizer_version,
            ),
        )

    def require_category(self, category_id: int) -> CocoLayoutCategoryAdmission:
        """Return one exact independently scoped category outcome."""
        return self.category_outcomes.require(category_id)
