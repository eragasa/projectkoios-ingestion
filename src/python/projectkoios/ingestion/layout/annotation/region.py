"""Human-authored semantic region annotations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.proposal.kind import LayoutRegionKind
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation
from projectkoios.ingestion.models import Metadata


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
    evidence: Metadata
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        case_id: str,
        kind: LayoutRegionKind,
        bounding_box_pixels: tuple[float, float, float, float],
        block_ids: tuple[str, ...],
        evidence: Metadata = (),
    ) -> LayoutRegionAnnotation:
        """Create one stable corrected-region annotation."""
        box = LayoutValueValidation.require_box(
            "bounding_box_pixels", bounding_box_pixels
        )
        normalized_evidence = LayoutValueValidation.normalize_metadata(evidence)
        annotation_id = stable_id(
            cls.CONTRACT_NAME,
            cls.CONTRACT_VERSION,
            case_id,
            kind,
            box,
            block_ids,
            normalized_evidence,
        )
        return cls(
            region_annotation_id=annotation_id,
            case_id=case_id,
            kind=kind,
            bounding_box_pixels=box,
            block_ids=block_ids,
            evidence=normalized_evidence,
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
        if len(set(self.block_ids)) != len(self.block_ids) or any(
            not block_id for block_id in self.block_ids
        ):
            raise ValueError("block_ids must contain unique non-empty IDs")
        evidence = LayoutValueValidation.normalize_metadata(self.evidence)
        object.__setattr__(self, "evidence", evidence)
        expected = stable_id(
            self.CONTRACT_NAME,
            self.CONTRACT_VERSION,
            self.case_id,
            self.kind,
            box,
            self.block_ids,
            evidence,
        )
        if self.region_annotation_id != expected:
            raise ValueError("layout region annotation ID is inconsistent")
