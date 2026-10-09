"""Deterministic reading-order resolution configuration."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.base.actionizer.configuration import (
    AbstractActionConfiguration,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation

from .limits import MAX_LAYOUT_READING_ORDER_ELEMENTS


@dataclass(frozen=True, slots=True)
class LayoutReadingOrderConfiguration(AbstractActionConfiguration):
    """Pin conservative geometry policy and bounded input size."""

    maximum_regions: int = MAX_LAYOUT_READING_ORDER_ELEMENTS
    maximum_native_blocks: int = MAX_LAYOUT_READING_ORDER_ELEMENTS
    configuration_id: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        regions = LayoutValueValidation.require_positive_integer(
            "maximum_regions",
            self.maximum_regions,
            maximum=MAX_LAYOUT_READING_ORDER_ELEMENTS,
        )
        blocks = LayoutValueValidation.require_positive_integer(
            "maximum_native_blocks",
            self.maximum_native_blocks,
            maximum=MAX_LAYOUT_READING_ORDER_ELEMENTS,
        )
        object.__setattr__(self, "maximum_regions", regions)
        object.__setattr__(self, "maximum_native_blocks", blocks)
        object.__setattr__(
            self,
            "configuration_id",
            stable_id(
                "layout-reading-order-configuration",
                regions,
                blocks,
            ),
        )
