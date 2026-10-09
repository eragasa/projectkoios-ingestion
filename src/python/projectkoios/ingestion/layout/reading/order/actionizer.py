"""Conservative deterministic reading-order verification and resolution."""

from __future__ import annotations

from projectkoios.base import DataObjectActionizer

from .derivation import derive_layout_reading_order_decision
from .request import LayoutReadingOrderRequest
from .result import LayoutReadingOrderResult


class DeterministicLayoutReadingOrderActionizer(
    DataObjectActionizer[
        LayoutReadingOrderRequest,
        LayoutReadingOrderResult,
    ]
):
    """Resolve only complete order mechanically supported by geometry."""

    __slots__ = ()

    def action(
        self, *, request: LayoutReadingOrderRequest
    ) -> LayoutReadingOrderResult:
        """Compare a candidate with conservative geometry-derived order."""
        status, reasons, resolution = derive_layout_reading_order_decision(
            request=request
        )
        return LayoutReadingOrderResult(
            request=request,
            status=status,
            reasons=reasons,
            resolution=resolution,
        )
