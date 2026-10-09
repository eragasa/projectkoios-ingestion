"""Project deterministic resolved layout into a strict COCO sidecar record."""

from __future__ import annotations

from projectkoios.base import DataObjectActionizer

from .derivation import derive_coco_layout_image_reading_order
from .request import CocoLayoutReadingOrderProjectionRequest
from .result import CocoLayoutReadingOrderProjectionResult


class CocoLayoutReadingOrderProjectionActionizer(
    DataObjectActionizer[
        CocoLayoutReadingOrderProjectionRequest,
        CocoLayoutReadingOrderProjectionResult,
    ]
):
    """Map proposal identities to exact canonical COCO annotation IDs."""

    __slots__ = ()

    def action(
        self, *, request: CocoLayoutReadingOrderProjectionRequest
    ) -> CocoLayoutReadingOrderProjectionResult:
        """Project only exact complete resolution and lineage agreement."""
        return CocoLayoutReadingOrderProjectionResult(
            request=request,
            reading_order=derive_coco_layout_image_reading_order(
                request=request
            ),
        )
