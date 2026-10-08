"""Immutable result of adapting frozen LayoutParser detections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.actionizer.result import (
    AbstractDataObjectActionResult,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.layout_parser.adaptation import (
    LayoutParserProposalAdaptation,
)
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
    """Expose exact request-bound proposals with complete adapter lineage."""

    CONTRACT_NAME: ClassVar[str] = "layout-parser-proposal-result"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    result_id: str
    request: LayoutParserProposalRequest
    proposal_source: LayoutRegionProposalSource
    adaptations: tuple[LayoutParserProposalAdaptation, ...]
    actionizer_name: str
    actionizer_version: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        request: LayoutParserProposalRequest,
        actionizer_name: str,
        actionizer_version: str,
    ) -> LayoutParserProposalResult:
        """Derive one stable result from the complete immutable request."""
        if type(request) is not LayoutParserProposalRequest:
            raise TypeError("request must be LayoutParserProposalRequest")
        source = cls.proposal_source_for(request)
        adaptations = cls.adaptations_for(request=request, source=source)
        actionizer = LayoutValueValidation.require_text(
            "actionizer_name", actionizer_name
        )
        actionizer_release = LayoutValueValidation.require_text(
            "actionizer_version", actionizer_version
        )
        result_id = stable_id(
            cls.CONTRACT_NAME,
            cls.CONTRACT_VERSION,
            request.request_id,
            source.proposal_source_id,
            tuple(adaptation.adaptation_id for adaptation in adaptations),
            actionizer,
            actionizer_release,
            request.configuration.configuration_id,
        )
        return cls(
            result_id=result_id,
            request=request,
            proposal_source=source,
            adaptations=adaptations,
            actionizer_name=actionizer,
            actionizer_version=actionizer_release,
        )

    @staticmethod
    def proposal_source_for(
        request: LayoutParserProposalRequest,
    ) -> LayoutRegionProposalSource:
        """Derive exact proposal-source identity from request configuration."""
        configuration = request.configuration
        return LayoutRegionProposalSource.create(
            detector_name=f"layoutparser:{configuration.backend_name}",
            detector_version=(
                f"{configuration.package_version}/"
                f"{configuration.backend_version}"
            ),
            resource_identity=configuration.model_identity,
            resource_sha256=configuration.model_sha256,
            configuration_id=configuration.configuration_id,
        )

    @staticmethod
    def adaptations_for(
        *,
        request: LayoutParserProposalRequest,
        source: LayoutRegionProposalSource,
    ) -> tuple[LayoutParserProposalAdaptation, ...]:
        """Derive exactly one proposal adaptation per request detection."""
        label_mapping = dict(request.configuration.label_mapping)
        return tuple(
            LayoutParserProposalAdaptation.create(
                detection_id=detection.detection_id,
                proposal=LayoutRegionProposal.create(
                    render_id=request.render.render_id,
                    proposal_source_id=source.proposal_source_id,
                    kind=label_mapping[detection.label],
                    bounding_box_pixels=detection.bounding_box_pixels,
                    confidence=detection.confidence,
                ),
            )
            for detection in request.detections
        )

    @property
    def request_id(self) -> str:
        """Return complete adaptation-request identity."""
        return self.request.request_id

    @property
    def render_id(self) -> str:
        """Return exact rendered-page identity."""
        return self.request.render.render_id

    @property
    def proposals(self) -> tuple[LayoutRegionProposal, ...]:
        """Return backend-neutral proposals in detection order."""
        return tuple(adaptation.proposal for adaptation in self.adaptations)

    @property
    def configuration_id(self) -> str:
        """Return request-bound configuration identity."""
        return self.request.configuration.configuration_id

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError(
                "unsupported LayoutParser proposal result contract"
            )
        if type(self.request) is not LayoutParserProposalRequest:
            raise TypeError("request must be LayoutParserProposalRequest")
        if type(self.proposal_source) is not LayoutRegionProposalSource:
            raise TypeError(
                "proposal_source must be LayoutRegionProposalSource"
            )
        if not isinstance(self.adaptations, tuple) or any(
            type(adaptation) is not LayoutParserProposalAdaptation
            for adaptation in self.adaptations
        ):
            raise TypeError(
                "adaptations must contain LayoutParserProposalAdaptation"
            )
        if len(
            {adaptation.adaptation_id for adaptation in self.adaptations}
        ) != len(self.adaptations):
            raise ValueError("adaptation IDs must be unique")
        expected_source = self.proposal_source_for(self.request)
        if self.proposal_source != expected_source:
            raise ValueError("proposal source differs from adaptation request")
        expected_adaptations = self.adaptations_for(
            request=self.request,
            source=expected_source,
        )
        if self.adaptations != expected_adaptations:
            raise ValueError("proposals differ from adaptation request")
        LayoutValueValidation.require_text(
            "actionizer_name", self.actionizer_name
        )
        LayoutValueValidation.require_text(
            "actionizer_version", self.actionizer_version
        )
        expected = stable_id(
            self.CONTRACT_NAME,
            self.CONTRACT_VERSION,
            self.request.request_id,
            self.proposal_source.proposal_source_id,
            tuple(adaptation.adaptation_id for adaptation in self.adaptations),
            self.actionizer_name,
            self.actionizer_version,
            self.request.configuration.configuration_id,
        )
        if self.result_id != expected:
            raise ValueError("LayoutParser proposal result ID is inconsistent")
