"""Exact COCO-detection to layout-proposal adaptations."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.detection import (
    CocoLayoutDetection,
)
from projectkoios.ingestion.integrations.coco.layout.limits.definition import (
    MAX_COCO_LAYOUT_DETECTIONS,
)
from projectkoios.ingestion.integrations.coco.layout.limits.error import (
    CocoLayoutLimitError,
)
from projectkoios.ingestion.layout.proposal.region import LayoutRegionProposal


@dataclass(frozen=True, slots=True)
class CocoLayoutProposalAdaptation(AbstractImmutableDataObject):
    """Bind one exact COCO detection to one backend-neutral proposal."""

    detection: CocoLayoutDetection
    proposal: LayoutRegionProposal
    adaptation_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.detection) is not CocoLayoutDetection:
            raise TypeError("detection must be CocoLayoutDetection")
        if type(self.proposal) is not LayoutRegionProposal:
            raise TypeError("proposal must be LayoutRegionProposal")
        object.__setattr__(
            self,
            "adaptation_id",
            stable_id(
                "coco-layout-proposal-adaptation",
                self.detection.detection_id,
                self.proposal.proposal_id,
            ),
        )


@dataclass(frozen=True, slots=True, init=False)
class CocoLayoutProposalAdaptationInventory:
    """Own ordered one-to-one COCO proposal adaptations."""

    _adaptations: tuple[CocoLayoutProposalAdaptation, ...] = field(repr=True)
    inventory_id: str = field(init=False)

    def __init__(self, *adaptations: CocoLayoutProposalAdaptation) -> None:
        values = tuple(adaptations)
        if len(values) > MAX_COCO_LAYOUT_DETECTIONS:
            raise CocoLayoutLimitError(
                "COCO adaptations exceed their implementation limit"
            )
        if any(
            type(value) is not CocoLayoutProposalAdaptation for value in values
        ):
            raise TypeError(
                "COCO adaptation inventory requires exact adaptations"
            )
        annotation_ids = tuple(
            value.detection.annotation_id for value in values
        )
        if annotation_ids != tuple(sorted(annotation_ids)):
            raise ValueError("COCO adaptations must follow annotation ID order")
        identities = tuple(value.adaptation_id for value in values)
        if len(identities) != len(set(identities)):
            raise ValueError("COCO adaptation identities must be unique")
        object.__setattr__(self, "_adaptations", values)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id("coco-layout-adaptation-inventory", identities),
        )

    def __iter__(self) -> Iterator[CocoLayoutProposalAdaptation]:
        return iter(self._adaptations)

    def __len__(self) -> int:
        return len(self._adaptations)
