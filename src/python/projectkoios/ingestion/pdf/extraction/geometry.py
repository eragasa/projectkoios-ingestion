"""Deterministic validation of backend PDF block geometry."""

from __future__ import annotations

import math
from dataclasses import dataclass

from projectkoios.base import (
    DataObjectActionizer,
    DataObjectActionRequest,
    DataObjectActionResult,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import BoundingBox

BLOCK_GEOMETRY_ACTION_CONTRACT_VERSION = "1.0"
BLOCK_GEOMETRY_ACTIONIZER_NAME = "deterministic-pdf-block-geometry-actionizer"
BLOCK_GEOMETRY_ACTIONIZER_VERSION = "1"


@dataclass(frozen=True, slots=True)
class BlockGeometryRequest(DataObjectActionRequest):
    """Bounded normalized backend coordinates for one PDF block."""

    request_id: str
    coordinates: tuple[float, ...]
    coordinate_count: int | None
    contract_version: str = BLOCK_GEOMETRY_ACTION_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        coordinates: tuple[float, ...] = (),
        coordinate_count: int | None = None,
    ) -> BlockGeometryRequest:
        request_id = stable_id(
            "pdf-block-geometry-request",
            coordinates,
            coordinate_count,
            BLOCK_GEOMETRY_ACTION_CONTRACT_VERSION,
        )
        return cls(
            request_id=request_id,
            coordinates=coordinates,
            coordinate_count=coordinate_count,
        )

    def __post_init__(self) -> None:
        if self.contract_version != BLOCK_GEOMETRY_ACTION_CONTRACT_VERSION:
            raise ValueError("unsupported block-geometry request contract")
        if not isinstance(self.coordinates, tuple) or any(
            not isinstance(item, float) for item in self.coordinates
        ):
            raise TypeError("coordinates must be an immutable float tuple")
        if len(self.coordinates) > 5:
            raise ValueError("coordinates exceed the bounded inspection limit")
        if self.coordinate_count is None:
            if self.coordinates:
                raise ValueError(
                    "unavailable geometry cannot contain coordinates"
                )
        elif (
            isinstance(self.coordinate_count, bool)
            or not isinstance(self.coordinate_count, int)
            or self.coordinate_count < len(self.coordinates)
        ):
            raise ValueError("coordinate_count is inconsistent")
        expected = stable_id(
            "pdf-block-geometry-request",
            self.coordinates,
            self.coordinate_count,
            self.contract_version,
        )
        if self.request_id != expected:
            raise ValueError("block-geometry request ID is inconsistent")


@dataclass(frozen=True, slots=True)
class BlockGeometry(DataObjectActionResult):
    """Identified valid geometry or an explicit invalidity classification."""

    result_id: str
    request_id: str
    bounding_box: BoundingBox | None
    invalid_reason: str | None
    raw_evidence: str
    actionizer_name: str
    actionizer_version: str
    contract_version: str = BLOCK_GEOMETRY_ACTION_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        request: BlockGeometryRequest,
        bounding_box: BoundingBox | None,
        invalid_reason: str | None,
        raw_evidence: str,
        actionizer_name: str,
        actionizer_version: str,
    ) -> BlockGeometry:
        result_id = stable_id(
            "pdf-block-geometry-result",
            request.request_id,
            bounding_box,
            invalid_reason,
            raw_evidence,
            actionizer_name,
            actionizer_version,
            BLOCK_GEOMETRY_ACTION_CONTRACT_VERSION,
        )
        return cls(
            result_id=result_id,
            request_id=request.request_id,
            bounding_box=bounding_box,
            invalid_reason=invalid_reason,
            raw_evidence=raw_evidence,
            actionizer_name=actionizer_name,
            actionizer_version=actionizer_version,
        )

    def __post_init__(self) -> None:
        if self.contract_version != BLOCK_GEOMETRY_ACTION_CONTRACT_VERSION:
            raise ValueError("unsupported block-geometry result contract")
        if not self.request_id:
            raise ValueError("request_id must be non-empty")
        if not self.raw_evidence or len(self.raw_evidence) > 256:
            raise ValueError("raw_evidence must be non-empty and bounded")
        if not self.actionizer_name or not self.actionizer_version:
            raise ValueError("actionizer identity must be complete")
        if (self.bounding_box is None) == (self.invalid_reason is None):
            raise ValueError(
                "block geometry must be either valid or explicitly invalid"
            )
        expected = stable_id(
            "pdf-block-geometry-result",
            self.request_id,
            self.bounding_box,
            self.invalid_reason,
            self.raw_evidence,
            self.actionizer_name,
            self.actionizer_version,
            self.contract_version,
        )
        if self.result_id != expected:
            raise ValueError("block-geometry result ID is inconsistent")


class BlockGeometryActionizer(
    DataObjectActionizer[BlockGeometryRequest, BlockGeometry]
):
    """Classify bounded backend geometry without repairing coordinates."""

    __slots__ = ()

    actionizer_name = BLOCK_GEOMETRY_ACTIONIZER_NAME
    actionizer_version = BLOCK_GEOMETRY_ACTIONIZER_VERSION

    def action(self, *, request: BlockGeometryRequest) -> BlockGeometry:
        if not isinstance(request, BlockGeometryRequest):
            raise TypeError("request must be a BlockGeometryRequest")
        evidence = (
            ",".join(format(item, ".17g") for item in request.coordinates)[:256]
            or "unavailable"
        )
        invalid_reason: str | None = None
        bounding_box: BoundingBox | None = None
        if request.coordinate_count != 4 or len(request.coordinates) != 4:
            invalid_reason = "malformed"
        elif not all(math.isfinite(item) for item in request.coordinates):
            invalid_reason = "non_finite"
        elif any(item < 0.0 for item in request.coordinates):
            invalid_reason = "negative_coordinate"
        else:
            x0, y0, x1, y1 = request.coordinates
            if x1 < x0 or y1 < y0:
                invalid_reason = "unordered"
            elif x1 == x0 or y1 == y0:
                invalid_reason = "non_positive_area"
            else:
                bounding_box = (x0, y0, x1, y1)
        return BlockGeometry.create(
            request=request,
            bounding_box=bounding_box,
            invalid_reason=invalid_reason,
            raw_evidence=evidence,
            actionizer_name=self.actionizer_name,
            actionizer_version=self.actionizer_version,
        )


__all__ = [
    "BLOCK_GEOMETRY_ACTION_CONTRACT_VERSION",
    "BLOCK_GEOMETRY_ACTIONIZER_NAME",
    "BLOCK_GEOMETRY_ACTIONIZER_VERSION",
    "BlockGeometry",
    "BlockGeometryActionizer",
    "BlockGeometryRequest",
]
