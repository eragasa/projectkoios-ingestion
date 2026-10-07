"""Typed one-to-one LayoutParser detection-to-proposal adaptations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.proposal.region import LayoutRegionProposal
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation


@dataclass(frozen=True, slots=True)
class LayoutParserProposalAdaptation(AbstractImmutableDataObject):
    """Bind one frozen LayoutParser detection to one domain proposal."""

    CONTRACT_NAME: ClassVar[str] = "layout-parser-proposal-adaptation"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    adaptation_id: str
    detection_id: str
    proposal: LayoutRegionProposal
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        detection_id: str,
        proposal: LayoutRegionProposal,
    ) -> LayoutParserProposalAdaptation:
        """Create one stable typed adaptation relation."""
        detection = LayoutValueValidation.require_text(
            "detection_id", detection_id
        )
        if type(proposal) is not LayoutRegionProposal:
            raise TypeError("proposal must be LayoutRegionProposal")
        adaptation_id = stable_id(
            cls.CONTRACT_NAME,
            cls.CONTRACT_VERSION,
            detection,
            proposal.proposal_id,
        )
        return cls(
            adaptation_id=adaptation_id,
            detection_id=detection,
            proposal=proposal,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported LayoutParser adaptation contract")
        LayoutValueValidation.require_text("detection_id", self.detection_id)
        if type(self.proposal) is not LayoutRegionProposal:
            raise TypeError("proposal must be LayoutRegionProposal")
        expected = stable_id(
            self.CONTRACT_NAME,
            self.CONTRACT_VERSION,
            self.detection_id,
            self.proposal.proposal_id,
        )
        if self.adaptation_id != expected:
            raise ValueError("LayoutParser adaptation ID is inconsistent")
