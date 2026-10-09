"""Explicit exclusions from local detector profile adaptation."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.limits.definition import (
    MAX_COCO_LAYOUT_DETECTIONS,
)
from projectkoios.ingestion.integrations.coco.layout.limits.error import (
    CocoLayoutLimitError,
)

from .observation import CocoLayoutDetectorObservation


class CocoLayoutDetectorLimitationCode(StrEnum):
    """Closed reasons why an observation did not enter the COCO profile."""

    UNSUPPORTED_LABEL = "unsupported_label"
    BELOW_CONFIDENCE_THRESHOLD = "below_confidence_threshold"


@dataclass(frozen=True, slots=True)
class CocoLayoutDetectorLimitation(AbstractImmutableDataObject):
    """Bind one excluded observation to one exact non-repairing reason."""

    observation: CocoLayoutDetectorObservation
    code: CocoLayoutDetectorLimitationCode
    limitation_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.observation) is not CocoLayoutDetectorObservation:
            raise TypeError("observation must be CocoLayoutDetectorObservation")
        if not isinstance(self.code, CocoLayoutDetectorLimitationCode):
            raise TypeError("code must be CocoLayoutDetectorLimitationCode")
        object.__setattr__(
            self,
            "limitation_id",
            stable_id(
                "coco-layout-detector-limitation",
                self.observation.observation_id,
                self.code,
            ),
        )


@dataclass(frozen=True, slots=True, init=False)
class CocoLayoutDetectorLimitationInventory:
    """Own bounded detector limitations in producer observation order."""

    _limitations: tuple[CocoLayoutDetectorLimitation, ...] = field(repr=True)
    inventory_id: str = field(init=False)

    def __init__(self, *limitations: CocoLayoutDetectorLimitation) -> None:
        values = tuple(limitations)
        if len(values) > MAX_COCO_LAYOUT_DETECTIONS:
            raise CocoLayoutLimitError(
                "detector limitations exceed their implementation limit"
            )
        if any(
            type(value) is not CocoLayoutDetectorLimitation for value in values
        ):
            raise TypeError(
                "detector limitation inventory requires exact limitations"
            )
        observation_ids = tuple(
            value.observation.observation_id for value in values
        )
        if len(observation_ids) != len(set(observation_ids)):
            raise ValueError(
                "each detector observation may have at most one limitation"
            )
        object.__setattr__(self, "_limitations", values)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id(
                "coco-layout-detector-limitation-inventory",
                tuple(value.limitation_id for value in values),
            ),
        )

    def __iter__(self) -> Iterator[CocoLayoutDetectorLimitation]:
        return iter(self._limitations)

    def __len__(self) -> int:
        return len(self._limitations)
