"""Immutable deterministic reading-order resolver results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.actionizer.result import (
    AbstractDataObjectActionResult,
)
from projectkoios.ingestion.identity import stable_id

from .derivation import derive_layout_reading_order_decision
from .kind import LayoutReadingOrderStatus
from .reason import LayoutReadingOrderReasonInventory
from .request import LayoutReadingOrderRequest
from .resolution import LayoutReadingOrderResolution


@dataclass(frozen=True, slots=True)
class LayoutReadingOrderResult(AbstractDataObjectActionResult):
    """Admit only mechanically complete and candidate-agreeing order."""

    ACTIONIZER_NAME: ClassVar[str] = (
        "deterministic-layout-reading-order-actionizer"
    )
    ACTIONIZER_VERSION: ClassVar[str] = "1"

    request: LayoutReadingOrderRequest
    status: LayoutReadingOrderStatus
    reasons: LayoutReadingOrderReasonInventory
    resolution: LayoutReadingOrderResolution | None
    result_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.request) is not LayoutReadingOrderRequest:
            raise TypeError("request must be LayoutReadingOrderRequest")
        if not isinstance(self.status, LayoutReadingOrderStatus):
            raise TypeError("status must be LayoutReadingOrderStatus")
        if type(self.reasons) is not LayoutReadingOrderReasonInventory:
            raise TypeError("reasons must be a reading-order reason inventory")
        if self.status is LayoutReadingOrderStatus.RESOLVED:
            if len(self.reasons) != 0:
                raise ValueError(
                    "resolved order cannot carry escalation reasons"
                )
            if type(self.resolution) is not LayoutReadingOrderResolution:
                raise ValueError("resolved status requires resolution evidence")
            expected_regions = {
                region.region_id for region in self.request.regions
            }
            if set(self.resolution.region_order) != expected_regions:
                raise ValueError("resolution must cover every region exactly")
            expected_blocks = set(self.request.expected_blocks)
            if set(self.resolution.native_block_order) != expected_blocks:
                raise ValueError(
                    "resolution must cover every native block exactly"
                )
        else:
            if len(self.reasons) == 0:
                raise ValueError("escalation requires at least one reason")
            if self.resolution is not None:
                raise ValueError("escalation cannot carry resolved order")
        expected = derive_layout_reading_order_decision(request=self.request)
        if (self.status, self.reasons, self.resolution) != expected:
            raise ValueError("reading-order result differs from derivation")
        object.__setattr__(
            self,
            "result_id",
            stable_id(
                "layout-reading-order-result",
                self.request.request_id,
                self.status,
                self.reasons.inventory_id,
                (
                    None
                    if self.resolution is None
                    else self.resolution.resolution_id
                ),
                self.ACTIONIZER_NAME,
                self.ACTIONIZER_VERSION,
            ),
        )
