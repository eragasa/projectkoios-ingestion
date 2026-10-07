"""Backend-neutral immutable layout-region proposals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.proposal.kind import LayoutRegionKind
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation
from projectkoios.ingestion.models import Metadata


@dataclass(frozen=True, slots=True)
class LayoutRegionProposal(AbstractImmutableDataObject):
    """Retain one unaccepted semantic region proposed over exact page pixels."""

    CONTRACT_NAME: ClassVar[str] = "layout-region-proposal"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    proposal_id: str
    render_id: str
    proposal_source_id: str
    kind: LayoutRegionKind
    bounding_box_pixels: tuple[float, float, float, float]
    confidence: float
    evidence: Metadata
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        render_id: str,
        proposal_source_id: str,
        kind: LayoutRegionKind,
        bounding_box_pixels: tuple[float, float, float, float],
        confidence: float,
        evidence: Metadata = (),
    ) -> LayoutRegionProposal:
        """Create one stable proposal without granting it authority."""
        box = LayoutValueValidation.require_box(
            "bounding_box_pixels", bounding_box_pixels
        )
        score = LayoutValueValidation.require_ratio("confidence", confidence)
        normalized_evidence = LayoutValueValidation.normalize_metadata(evidence)
        proposal_id = stable_id(
            cls.CONTRACT_NAME,
            cls.CONTRACT_VERSION,
            render_id,
            proposal_source_id,
            kind,
            box,
            score,
            normalized_evidence,
        )
        return cls(
            proposal_id=proposal_id,
            render_id=render_id,
            proposal_source_id=proposal_source_id,
            kind=kind,
            bounding_box_pixels=box,
            confidence=score,
            evidence=normalized_evidence,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported layout region proposal contract")
        LayoutValueValidation.require_text("render_id", self.render_id)
        LayoutValueValidation.require_text(
            "proposal_source_id", self.proposal_source_id
        )
        if not isinstance(self.kind, LayoutRegionKind):
            raise TypeError("kind must be LayoutRegionKind")
        box = LayoutValueValidation.require_box(
            "bounding_box_pixels", self.bounding_box_pixels
        )
        object.__setattr__(self, "bounding_box_pixels", box)
        score = LayoutValueValidation.require_ratio(
            "confidence", self.confidence
        )
        object.__setattr__(self, "confidence", score)
        evidence = LayoutValueValidation.normalize_metadata(self.evidence)
        object.__setattr__(self, "evidence", evidence)
        expected = stable_id(
            self.CONTRACT_NAME,
            self.CONTRACT_VERSION,
            self.render_id,
            self.proposal_source_id,
            self.kind,
            box,
            score,
            evidence,
        )
        if self.proposal_id != expected:
            raise ValueError("layout region proposal ID is inconsistent")
