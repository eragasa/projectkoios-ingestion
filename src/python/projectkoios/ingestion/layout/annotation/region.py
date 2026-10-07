"""Human-authored semantic region annotations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.annotation.limits.definition import (
    MAX_LAYOUT_REFERENCES_PER_ANNOTATION,
)
from projectkoios.ingestion.layout.annotation.limits.error import (
    LayoutAnnotationLimitError,
)
from projectkoios.ingestion.layout.proposal.kind import LayoutRegionKind
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation


@dataclass(frozen=True, slots=True)
class LayoutRegionAnnotation(AbstractImmutableDataObject):
    """Record one corrected region and its exact native block membership."""

    CONTRACT_NAME: ClassVar[str] = "layout-region-annotation"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    region_annotation_id: str
    case_id: str
    kind: LayoutRegionKind
    bounding_box_pixels: tuple[float, float, float, float]
    block_ids: tuple[str, ...]
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        case_id: str,
        kind: LayoutRegionKind,
        bounding_box_pixels: tuple[float, float, float, float],
        block_ids: tuple[str, ...],
    ) -> LayoutRegionAnnotation:
        """Create one stable corrected-region annotation."""
        case = LayoutValueValidation.require_text("case_id", case_id)
        if not isinstance(kind, LayoutRegionKind):
            raise TypeError("kind must be LayoutRegionKind")
        if not isinstance(block_ids, tuple):
            raise TypeError("block_ids must be a tuple")
        if len(block_ids) > MAX_LAYOUT_REFERENCES_PER_ANNOTATION:
            raise LayoutAnnotationLimitError(
                "block_ids exceed annotation implementation maximum"
            )
        if any(
            not isinstance(block_id, str) or not block_id
            for block_id in block_ids
        ):
            raise ValueError("block_ids must contain non-empty IDs")
        bounded_block_ids = tuple(
            LayoutValueValidation.require_text("block_id", block_id)
            for block_id in block_ids
        )
        if len(set(bounded_block_ids)) != len(bounded_block_ids):
            raise ValueError("block_ids must be unique")
        box = LayoutValueValidation.require_box(
            "bounding_box_pixels", bounding_box_pixels
        )
        annotation_id = stable_id(
            cls.CONTRACT_NAME,
            cls.CONTRACT_VERSION,
            case,
            kind,
            box,
            bounded_block_ids,
        )
        return cls(
            region_annotation_id=annotation_id,
            case_id=case,
            kind=kind,
            bounding_box_pixels=box,
            block_ids=bounded_block_ids,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported layout region annotation contract")
        LayoutValueValidation.require_text("case_id", self.case_id)
        if not isinstance(self.kind, LayoutRegionKind):
            raise TypeError("kind must be LayoutRegionKind")
        box = LayoutValueValidation.require_box(
            "bounding_box_pixels", self.bounding_box_pixels
        )
        object.__setattr__(self, "bounding_box_pixels", box)
        if not isinstance(self.block_ids, tuple):
            raise TypeError("block_ids must be a tuple")
        if len(self.block_ids) > MAX_LAYOUT_REFERENCES_PER_ANNOTATION:
            raise LayoutAnnotationLimitError(
                "block_ids exceed annotation implementation maximum"
            )
        if any(
            not isinstance(block_id, str) or not block_id
            for block_id in self.block_ids
        ):
            raise ValueError("block_ids must contain non-empty IDs")
        bounded_block_ids = tuple(
            LayoutValueValidation.require_text("block_id", block_id)
            for block_id in self.block_ids
        )
        if len(set(bounded_block_ids)) != len(bounded_block_ids):
            raise ValueError("block_ids must be unique")
        expected = stable_id(
            self.CONTRACT_NAME,
            self.CONTRACT_VERSION,
            self.case_id,
            self.kind,
            box,
            self.block_ids,
        )
        if self.region_annotation_id != expected:
            raise ValueError("layout region annotation ID is inconsistent")
