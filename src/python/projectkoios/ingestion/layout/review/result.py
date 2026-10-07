"""Immutable prepared layout review case."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.actionizer.result import (
    AbstractDataObjectActionResult,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.review.kind import LayoutReviewReason
from projectkoios.ingestion.layout.review.overlap import (
    LayoutBlockRegionOverlap,
)
from projectkoios.ingestion.layout.review.request import LayoutReviewRequest
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation


@dataclass(frozen=True, slots=True)
class LayoutReviewCase(AbstractDataObjectActionResult):
    """Present exact baseline and proposal evidence for external annotation."""

    CONTRACT_NAME: ClassVar[str] = "layout-review-case"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    case_id: str
    request_id: str
    layout_result_id: str
    render_id: str
    proposal_source_id: str
    proposal_ids: tuple[str, ...]
    image_width: int
    image_height: int
    overlaps: tuple[LayoutBlockRegionOverlap, ...]
    covered_block_ids: tuple[str, ...]
    uncovered_block_ids: tuple[str, ...]
    invalid_geometry_block_ids: tuple[str, ...]
    page_coverage_ratio: float
    reasons: tuple[LayoutReviewReason, ...]
    requires_review: bool
    actionizer_name: str
    actionizer_version: str
    configuration_id: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        request: LayoutReviewRequest,
        overlaps: tuple[LayoutBlockRegionOverlap, ...],
        covered_block_ids: tuple[str, ...],
        uncovered_block_ids: tuple[str, ...],
        invalid_geometry_block_ids: tuple[str, ...],
        page_coverage_ratio: float,
        reasons: tuple[LayoutReviewReason, ...],
        actionizer_name: str,
        actionizer_version: str,
    ) -> LayoutReviewCase:
        """Create one stable case from deterministic comparison output."""
        ratio = LayoutValueValidation.require_ratio(
            "page_coverage_ratio", page_coverage_ratio
        )
        proposal_ids = tuple(
            proposal.proposal_id for proposal in request.proposals
        )
        case_id = stable_id(
            cls.CONTRACT_NAME,
            cls.CONTRACT_VERSION,
            request.request_id,
            request.layout.result_id,
            request.render.render_id,
            request.proposal_source.proposal_source_id,
            proposal_ids,
            request.render.image_width,
            request.render.image_height,
            tuple(overlap.overlap_id for overlap in overlaps),
            covered_block_ids,
            uncovered_block_ids,
            invalid_geometry_block_ids,
            ratio,
            reasons,
            actionizer_name,
            actionizer_version,
            request.configuration.configuration_id,
        )
        return cls(
            case_id=case_id,
            request_id=request.request_id,
            layout_result_id=request.layout.result_id,
            render_id=request.render.render_id,
            proposal_source_id=request.proposal_source.proposal_source_id,
            proposal_ids=proposal_ids,
            image_width=request.render.image_width,
            image_height=request.render.image_height,
            overlaps=overlaps,
            covered_block_ids=covered_block_ids,
            uncovered_block_ids=uncovered_block_ids,
            invalid_geometry_block_ids=invalid_geometry_block_ids,
            page_coverage_ratio=ratio,
            reasons=reasons,
            requires_review=bool(reasons),
            actionizer_name=actionizer_name,
            actionizer_version=actionizer_version,
            configuration_id=request.configuration.configuration_id,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported layout review case contract")
        for name, value in (
            ("request_id", self.request_id),
            ("layout_result_id", self.layout_result_id),
            ("render_id", self.render_id),
            ("proposal_source_id", self.proposal_source_id),
            ("actionizer_name", self.actionizer_name),
            ("actionizer_version", self.actionizer_version),
            ("configuration_id", self.configuration_id),
        ):
            LayoutValueValidation.require_text(name, value)
        LayoutValueValidation.require_positive_integer(
            "image_width", self.image_width
        )
        LayoutValueValidation.require_positive_integer(
            "image_height", self.image_height
        )
        for name, values in (
            ("proposal_ids", self.proposal_ids),
            ("covered_block_ids", self.covered_block_ids),
            ("uncovered_block_ids", self.uncovered_block_ids),
            ("invalid_geometry_block_ids", self.invalid_geometry_block_ids),
        ):
            if not isinstance(values, tuple):
                raise TypeError(f"{name} must be a tuple")
            if len(set(values)) != len(values) or any(
                not value for value in values
            ):
                raise ValueError(f"{name} must contain unique non-empty IDs")
        partitions = (
            set(self.covered_block_ids),
            set(self.uncovered_block_ids),
            set(self.invalid_geometry_block_ids),
        )
        if (
            partitions[0] & partitions[1]
            or partitions[0] & partitions[2]
            or partitions[1] & partitions[2]
        ):
            raise ValueError("layout review block partitions must be disjoint")
        all_block_ids = partitions[0] | partitions[1] | partitions[2]
        if not isinstance(self.overlaps, tuple) or any(
            type(overlap) is not LayoutBlockRegionOverlap
            for overlap in self.overlaps
        ):
            raise TypeError("overlaps must contain LayoutBlockRegionOverlap")
        if len({overlap.overlap_id for overlap in self.overlaps}) != len(
            self.overlaps
        ):
            raise ValueError("overlap IDs must be unique")
        if any(
            overlap.render_id != self.render_id
            or overlap.block_id not in all_block_ids
            or overlap.proposal_id not in self.proposal_ids
            for overlap in self.overlaps
        ):
            raise ValueError("overlap identity differs from review case")
        if not isinstance(self.reasons, tuple) or any(
            not isinstance(reason, LayoutReviewReason)
            for reason in self.reasons
        ):
            raise TypeError("reasons must contain LayoutReviewReason")
        if tuple(sorted(set(self.reasons), key=str)) != self.reasons:
            raise ValueError("reasons must be unique and sorted")
        ratio = LayoutValueValidation.require_ratio(
            "page_coverage_ratio", self.page_coverage_ratio
        )
        expected_ratio = (
            1.0
            if not all_block_ids
            else round(len(self.covered_block_ids) / len(all_block_ids), 12)
        )
        if ratio != expected_ratio:
            raise ValueError(
                "page coverage ratio differs from block partitions"
            )
        object.__setattr__(self, "page_coverage_ratio", ratio)
        if self.requires_review is not bool(self.reasons):
            raise ValueError("requires_review must match reasons")
        expected = stable_id(
            self.CONTRACT_NAME,
            self.CONTRACT_VERSION,
            self.request_id,
            self.layout_result_id,
            self.render_id,
            self.proposal_source_id,
            self.proposal_ids,
            self.image_width,
            self.image_height,
            tuple(overlap.overlap_id for overlap in self.overlaps),
            self.covered_block_ids,
            self.uncovered_block_ids,
            self.invalid_geometry_block_ids,
            ratio,
            self.reasons,
            self.actionizer_name,
            self.actionizer_version,
            self.configuration_id,
        )
        if self.case_id != expected:
            raise ValueError("layout review case ID is inconsistent")
