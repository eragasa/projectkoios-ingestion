"""Deterministic layout review preparation configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.actionizer.configuration import (
    AbstractActionConfiguration,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.proposal.limits.definition import (
    MAX_LAYOUT_REGION_PROPOSALS,
)
from projectkoios.ingestion.layout.review.limits.definition import (
    MAX_LAYOUT_REVIEW_BLOCKS,
    MAX_LAYOUT_REVIEW_COMPARISONS,
    MAX_LAYOUT_REVIEW_OVERLAPS,
)
from projectkoios.ingestion.layout.review.limits.error import (
    LayoutReviewLimitError,
)
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation


@dataclass(frozen=True, slots=True)
class LayoutReviewConfiguration(AbstractActionConfiguration):
    """Bind coverage thresholds and hard limits for review preparation."""

    CONTRACT_NAME: ClassVar[str] = "layout-review-configuration"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    minimum_block_intersection_ratio: float = 0.5
    minimum_page_coverage_ratio: float = 0.9
    max_blocks: int = MAX_LAYOUT_REVIEW_BLOCKS
    max_proposals: int = MAX_LAYOUT_REGION_PROPOSALS
    max_comparisons: int = MAX_LAYOUT_REVIEW_COMPARISONS
    max_overlaps: int = MAX_LAYOUT_REVIEW_OVERLAPS
    configuration_id: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        block_ratio = LayoutValueValidation.require_ratio(
            "minimum_block_intersection_ratio",
            self.minimum_block_intersection_ratio,
        )
        page_ratio = LayoutValueValidation.require_ratio(
            "minimum_page_coverage_ratio", self.minimum_page_coverage_ratio
        )
        if block_ratio == 0.0 or page_ratio == 0.0:
            raise ValueError("layout review coverage ratios must exceed zero")
        object.__setattr__(
            self, "minimum_block_intersection_ratio", block_ratio
        )
        object.__setattr__(self, "minimum_page_coverage_ratio", page_ratio)
        for name, maximum in (
            ("max_blocks", MAX_LAYOUT_REVIEW_BLOCKS),
            ("max_proposals", MAX_LAYOUT_REGION_PROPOSALS),
            ("max_comparisons", MAX_LAYOUT_REVIEW_COMPARISONS),
            ("max_overlaps", MAX_LAYOUT_REVIEW_OVERLAPS),
        ):
            value = LayoutValueValidation.require_positive_integer(
                name, getattr(self, name)
            )
            if value > maximum:
                raise LayoutReviewLimitError(
                    f"{name} exceeds implementation maximum ({maximum})"
                )
        object.__setattr__(self, "configuration_id", self.configuration_digest)

    @property
    def configuration_digest(self) -> str:
        """Return stable identity over every review preparation choice."""
        return stable_id(
            self.CONTRACT_NAME,
            self.CONTRACT_VERSION,
            self.minimum_block_intersection_ratio,
            self.minimum_page_coverage_ratio,
            self.max_blocks,
            self.max_proposals,
            self.max_comparisons,
            self.max_overlaps,
        )
