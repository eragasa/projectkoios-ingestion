"""Immutable result of adapting frozen LayoutParser detections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.actionizer.result import (
    AbstractDataObjectActionResult,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.layout_parser.request import (
    LayoutParserProposalRequest,
)
from projectkoios.ingestion.layout.proposal.region import LayoutRegionProposal
from projectkoios.ingestion.layout.proposal.source import (
    LayoutRegionProposalSource,
)
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation


@dataclass(frozen=True, slots=True)
class LayoutParserProposalResult(AbstractDataObjectActionResult):
    """Expose backend-neutral proposals while retaining LayoutParser lineage."""

    CONTRACT_NAME: ClassVar[str] = "layout-parser-proposal-result"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    result_id: str
    request_id: str
    render_id: str
    proposal_source: LayoutRegionProposalSource
    proposals: tuple[LayoutRegionProposal, ...]
    actionizer_name: str
    actionizer_version: str
    configuration_id: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        request: LayoutParserProposalRequest,
        proposal_source: LayoutRegionProposalSource,
        proposals: tuple[LayoutRegionProposal, ...],
        actionizer_name: str,
        actionizer_version: str,
    ) -> LayoutParserProposalResult:
        """Create one stable adapter result."""
        result_id = stable_id(
            cls.CONTRACT_NAME,
            cls.CONTRACT_VERSION,
            request.request_id,
            request.render.render_id,
            proposal_source.proposal_source_id,
            tuple(proposal.proposal_id for proposal in proposals),
            actionizer_name,
            actionizer_version,
            request.configuration.configuration_id,
        )
        return cls(
            result_id=result_id,
            request_id=request.request_id,
            render_id=request.render.render_id,
            proposal_source=proposal_source,
            proposals=proposals,
            actionizer_name=actionizer_name,
            actionizer_version=actionizer_version,
            configuration_id=request.configuration.configuration_id,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError(
                "unsupported LayoutParser proposal result contract"
            )
        for name, value in (
            ("request_id", self.request_id),
            ("render_id", self.render_id),
            ("actionizer_name", self.actionizer_name),
            ("actionizer_version", self.actionizer_version),
            ("configuration_id", self.configuration_id),
        ):
            LayoutValueValidation.require_text(name, value)
        if type(self.proposal_source) is not LayoutRegionProposalSource:
            raise TypeError(
                "proposal_source must be LayoutRegionProposalSource"
            )
        if not isinstance(self.proposals, tuple) or any(
            type(proposal) is not LayoutRegionProposal
            for proposal in self.proposals
        ):
            raise TypeError("proposals must contain LayoutRegionProposal")
        if len({proposal.proposal_id for proposal in self.proposals}) != len(
            self.proposals
        ):
            raise ValueError("proposal IDs must be unique")
        if any(
            proposal.proposal_source_id
            != self.proposal_source.proposal_source_id
            for proposal in self.proposals
        ):
            raise ValueError("proposal source identity differs")
        if any(
            proposal.render_id != self.render_id for proposal in self.proposals
        ):
            raise ValueError("proposal render identity differs")
        expected = stable_id(
            self.CONTRACT_NAME,
            self.CONTRACT_VERSION,
            self.request_id,
            self.render_id,
            self.proposal_source.proposal_source_id,
            tuple(proposal.proposal_id for proposal in self.proposals),
            self.actionizer_name,
            self.actionizer_version,
            self.configuration_id,
        )
        if self.result_id != expected:
            raise ValueError("LayoutParser proposal result ID is inconsistent")
