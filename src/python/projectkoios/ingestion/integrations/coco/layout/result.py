"""Immutable result of adapting exact COCO layout detections."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.actionizer.result import (
    AbstractDataObjectActionResult,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.adaptation import (
    CocoLayoutProposalAdaptation,
    CocoLayoutProposalAdaptationInventory,
)
from projectkoios.ingestion.integrations.coco.layout.request import (
    CocoLayoutProposalRequest,
)
from projectkoios.ingestion.layout.proposal.region import LayoutRegionProposal
from projectkoios.ingestion.layout.proposal.source import (
    LayoutRegionProposalSource,
)


@dataclass(frozen=True, slots=True)
class CocoLayoutProposalResult(AbstractDataObjectActionResult):
    """Expose request-reconstructed proposals with exact COCO lineage."""

    CONTRACT_NAME: ClassVar[str] = "coco-layout-proposal-result"
    CONTRACT_VERSION: ClassVar[str] = "1.0"
    ACTIONIZER_NAME: ClassVar[str] = "coco-layout-proposal-adapter"
    ACTIONIZER_VERSION: ClassVar[str] = "1.0"

    request: CocoLayoutProposalRequest
    proposal_source: LayoutRegionProposalSource = field(init=False)
    adaptations: CocoLayoutProposalAdaptationInventory = field(init=False)
    result_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.request) is not CocoLayoutProposalRequest:
            raise TypeError("request must be CocoLayoutProposalRequest")
        configuration = self.request.configuration
        source = LayoutRegionProposalSource.create(
            detector_name=f"coco:{configuration.detector_name}",
            detector_version=(
                f"{configuration.detector_version}/"
                f"{configuration.runtime_name}-"
                f"{configuration.runtime_version}"
            ),
            resource_identity=configuration.resource_identity,
            resource_sha256=configuration.resource_sha256,
            configuration_id=configuration.configuration_id,
        )
        adaptations = CocoLayoutProposalAdaptationInventory(
            *(
                CocoLayoutProposalAdaptation(
                    detection=detection,
                    proposal=LayoutRegionProposal.create(
                        render_id=self.request.render.render_id,
                        proposal_source_id=source.proposal_source_id,
                        kind=configuration.profile.categories.require(
                            detection.category_id
                        ).kind,
                        bounding_box_pixels=detection.bounding_box_pixels,
                        confidence=detection.confidence,
                    ),
                )
                for detection in self.request.detections
            )
        )
        object.__setattr__(self, "proposal_source", source)
        object.__setattr__(self, "adaptations", adaptations)
        object.__setattr__(
            self,
            "result_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                self.request.request_id,
                source.proposal_source_id,
                adaptations.inventory_id,
                self.ACTIONIZER_NAME,
                self.ACTIONIZER_VERSION,
            ),
        )

    @property
    def proposals(self) -> tuple[LayoutRegionProposal, ...]:
        """Return backend-neutral proposals in COCO annotation order."""
        return tuple(adaptation.proposal for adaptation in self.adaptations)
