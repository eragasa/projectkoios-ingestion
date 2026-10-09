"""Deterministic projection of admitted COCO formulas."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.base.actionizer.result import (
    AbstractDataObjectActionResult,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.adaptation import (
    CocoLayoutProposalAdaptation,
)
from projectkoios.ingestion.integrations.coco.layout.admission.overlap import (
    coco_layout_intersection_over_union,
)
from projectkoios.ingestion.layout.proposal.kind import LayoutRegionKind
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation
from projectkoios.ingestion.models import SourceSpan

from .candidate import (
    CocoLayoutEquationCandidateEvidence,
    CocoLayoutEquationCandidateEvidenceInventory,
)
from .exclusion import (
    CocoLayoutEquationExclusion,
    CocoLayoutEquationExclusionCode,
    CocoLayoutEquationExclusionInventory,
)
from .request import CocoLayoutEquationProjectionRequest


@dataclass(frozen=True, slots=True)
class CocoLayoutEquationProjectionResult(AbstractDataObjectActionResult):
    """Expose exact formula candidates and every formula-only exclusion."""

    request: CocoLayoutEquationProjectionRequest
    candidates: CocoLayoutEquationCandidateEvidenceInventory
    exclusions: CocoLayoutEquationExclusionInventory
    actionizer_name: str
    actionizer_version: str
    result_id: str = field(init=False)

    @classmethod
    def create(
        cls,
        *,
        request: CocoLayoutEquationProjectionRequest,
        actionizer_name: str,
        actionizer_version: str,
    ) -> CocoLayoutEquationProjectionResult:
        """Derive the only candidate and exclusion inventories."""
        candidates, exclusions = cls.derive(request)
        return cls(
            request=request,
            candidates=candidates,
            exclusions=exclusions,
            actionizer_name=actionizer_name,
            actionizer_version=actionizer_version,
        )

    @classmethod
    def derive(
        cls, request: CocoLayoutEquationProjectionRequest
    ) -> tuple[
        CocoLayoutEquationCandidateEvidenceInventory,
        CocoLayoutEquationExclusionInventory,
    ]:
        """Project admitted formulas with deterministic confidence and NMS."""
        if type(request) is not CocoLayoutEquationProjectionRequest:
            raise TypeError(
                "request must be CocoLayoutEquationProjectionRequest"
            )
        configuration = request.configuration
        formula_adaptations = tuple(
            request.formula_admission.admitted_adaptations
        )
        if any(
            adaptation.proposal.kind is not LayoutRegionKind.EQUATION
            for adaptation in formula_adaptations
        ):
            raise ValueError("formula admission contains a non-formula region")
        qualified: list[CocoLayoutProposalAdaptation] = []
        exclusions: list[CocoLayoutEquationExclusion] = []
        for adaptation in formula_adaptations:
            if (
                adaptation.proposal.confidence
                < configuration.minimum_confidence
            ):
                exclusions.append(
                    CocoLayoutEquationExclusion(
                        projection_request_id=request.request_id,
                        adaptation=adaptation,
                        code=(
                            CocoLayoutEquationExclusionCode.BELOW_CONFIDENCE_THRESHOLD
                        ),
                        selected_candidate_id=None,
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
        selected: list[
            tuple[
                CocoLayoutProposalAdaptation,
                CocoLayoutEquationCandidateEvidence,
            ]
        ] = []
        render = request.admission_result.request.detector_result.request.render
        mapping = render.mapping
        page = next(
            page
            for page in request.document.pages
            if page.page_index == render.page_index
        )
        for adaptation in qualified:
            duplicate = next(
                (
                    candidate
                    for retained, candidate in selected
                    if coco_layout_intersection_over_union(
                        retained.proposal.bounding_box_pixels,
                        adaptation.proposal.bounding_box_pixels,
                    )
                    >= configuration.duplicate_iou_threshold
                ),
                None,
            )
            if duplicate is not None:
                exclusions.append(
                    CocoLayoutEquationExclusion(
                        projection_request_id=request.request_id,
                        adaptation=adaptation,
                        code=CocoLayoutEquationExclusionCode.DUPLICATE_OVERLAP,
                        selected_candidate_id=duplicate.candidate_id,
                    )
                )
                continue
            mapped = mapping.pixel_box_to_source_box(
                adaptation.proposal.bounding_box_pixels
            )
            padding = configuration.source_padding_points
            source_box = (
                max(0.0, mapped[0] - padding),
                max(0.0, mapped[1] - padding),
                min(page.width, mapped[2] + padding),
                min(page.height, mapped[3] + padding),
            )
            candidate = CocoLayoutEquationCandidateEvidence(
                projection_request_id=request.request_id,
                admission_result_id=request.admission_result.result_id,
                document_id=request.document.document_id,
                source_content_hash=request.document.source.content_hash,
                render=render,
                detection_id=adaptation.detection.detection_id,
                pixel_bounding_box=(adaptation.detection.bounding_box_pixels),
                mapped_source_bounding_box=mapped,
                adaptation=adaptation,
                source_span=SourceSpan(
                    source_id=request.document.source.source_id,
                    source_blob_id=request.document.source.blob_id,
                    page_index=page.page_index,
                    printed_page_label=page.printed_page_label,
                    source_object_id=adaptation.proposal.proposal_id,
                    bounding_box=source_box,
                ),
            )
            selected.append((adaptation, candidate))
            if len(selected) > configuration.maximum_candidates:
                raise ValueError(
                    "equation candidates exceed the configured maximum"
                )
        candidates = tuple(
            sorted(
                (candidate for _adaptation, candidate in selected),
                key=coco_layout_equation_candidate_order,
            )
        )
        ordered_exclusions = tuple(
            sorted(
                exclusions,
                key=lambda value: (
                    value.adaptation.proposal.proposal_id,
                    value.code,
                    value.exclusion_id,
                ),
            )
        )
        return (
            CocoLayoutEquationCandidateEvidenceInventory(*candidates),
            CocoLayoutEquationExclusionInventory(*ordered_exclusions),
        )

    def __post_init__(self) -> None:
        if type(self.request) is not CocoLayoutEquationProjectionRequest:
            raise TypeError(
                "request must be CocoLayoutEquationProjectionRequest"
            )
        if type(self.candidates) is not (
            CocoLayoutEquationCandidateEvidenceInventory
        ):
            raise TypeError("candidates must be a candidate inventory")
        if type(self.exclusions) is not CocoLayoutEquationExclusionInventory:
            raise TypeError("exclusions must be an exclusion inventory")
        actionizer_name = LayoutValueValidation.require_text(
            "actionizer_name", self.actionizer_name
        )
        actionizer_version = LayoutValueValidation.require_text(
            "actionizer_version", self.actionizer_version
        )
        expected_candidates, expected_exclusions = self.derive(self.request)
        if (
            self.candidates != expected_candidates
            or self.exclusions != expected_exclusions
        ):
            raise ValueError(
                "equation projection differs from deterministic derivation"
            )
        object.__setattr__(self, "actionizer_name", actionizer_name)
        object.__setattr__(self, "actionizer_version", actionizer_version)
        object.__setattr__(
            self,
            "result_id",
            stable_id(
                "coco-layout-equation-projection-result",
                self.request.request_id,
                self.candidates.inventory_id,
                self.exclusions.inventory_id,
                actionizer_name,
                actionizer_version,
            ),
        )


def coco_layout_equation_candidate_order(
    candidate: CocoLayoutEquationCandidateEvidence,
) -> tuple[int, float, float, float, float, str]:
    """Return canonical source order for one projected formula candidate."""
    box = candidate.source_span.bounding_box
    if box is None:
        raise ValueError("equation candidate source geometry is missing")
    return (
        candidate.source_span.page_index,
        box[1],
        box[0],
        box[3],
        box[2],
        candidate.candidate_id,
    )
