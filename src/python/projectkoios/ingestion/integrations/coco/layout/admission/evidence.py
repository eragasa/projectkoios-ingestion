"""Per-detection evidence from generic COCO region admission."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.adaptation import (
    CocoLayoutProposalAdaptation,
)
from projectkoios.ingestion.integrations.coco.layout.limits.definition import (
    MAX_COCO_LAYOUT_DETECTIONS,
)
from projectkoios.ingestion.integrations.coco.layout.limits.error import (
    CocoLayoutLimitError,
)


class CocoLayoutRegionAdmissionDisposition(StrEnum):
    """Closed dispositions for one supported COCO proposal adaptation."""

    ADMITTED = "admitted"
    EXCLUDED_BELOW_CONFIDENCE = "excluded_below_confidence"
    EXCLUDED_DUPLICATE = "excluded_duplicate"
    ESCALATION_REQUIRED_LIMIT = "escalation_required_limit"


@dataclass(frozen=True, slots=True)
class CocoLayoutRegionAdmissionEvidence(AbstractImmutableDataObject):
    """Bind one proposal adaptation to one scoped admission disposition."""

    admission_request_id: str
    adaptation: CocoLayoutProposalAdaptation
    disposition: CocoLayoutRegionAdmissionDisposition
    selected_adaptation_id: str | None
    evidence_id: str = field(init=False)

    def __post_init__(self) -> None:
        if not self.admission_request_id:
            raise ValueError("admission_request_id must be non-empty")
        if type(self.adaptation) is not CocoLayoutProposalAdaptation:
            raise TypeError("adaptation must be CocoLayoutProposalAdaptation")
        if not isinstance(
            self.disposition, CocoLayoutRegionAdmissionDisposition
        ):
            raise TypeError("disposition must be an admission disposition")
        if (
            self.disposition
            is CocoLayoutRegionAdmissionDisposition.EXCLUDED_DUPLICATE
        ):
            if not self.selected_adaptation_id:
                raise ValueError(
                    "duplicate exclusion requires selected lineage"
                )
            if self.selected_adaptation_id == self.adaptation.adaptation_id:
                raise ValueError("duplicate cannot select itself")
        elif self.selected_adaptation_id is not None:
            raise ValueError(
                "only duplicate exclusion may identify a selected adaptation"
            )
        object.__setattr__(
            self,
            "evidence_id",
            stable_id(
                "coco-layout-region-admission-evidence",
                self.admission_request_id,
                self.adaptation.adaptation_id,
                self.disposition,
                self.selected_adaptation_id,
            ),
        )


@dataclass(frozen=True, slots=True, init=False)
class CocoLayoutRegionAdmissionEvidenceInventory:
    """Own annotation-ordered admission evidence without raw public tuples."""

    _evidence: tuple[CocoLayoutRegionAdmissionEvidence, ...] = field(repr=True)
    inventory_id: str = field(init=False)

    def __init__(self, *evidence: CocoLayoutRegionAdmissionEvidence) -> None:
        values = tuple(evidence)
        if len(values) > MAX_COCO_LAYOUT_DETECTIONS:
            raise CocoLayoutLimitError(
                "region admission evidence exceeds its count limit"
            )
        if any(
            type(value) is not CocoLayoutRegionAdmissionEvidence
            for value in values
        ):
            raise TypeError("admission inventory requires exact evidence")
        annotation_ids = tuple(
            value.adaptation.detection.annotation_id for value in values
        )
        if annotation_ids != tuple(sorted(annotation_ids)):
            raise ValueError("admission evidence must follow annotation order")
        if len(annotation_ids) != len(set(annotation_ids)):
            raise ValueError("admission evidence must be unique per detection")
        object.__setattr__(self, "_evidence", values)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id(
                "coco-layout-region-admission-evidence-inventory",
                tuple(value.evidence_id for value in values),
            ),
        )

    def __iter__(self) -> Iterator[CocoLayoutRegionAdmissionEvidence]:
        return iter(self._evidence)

    def __len__(self) -> int:
        return len(self._evidence)
