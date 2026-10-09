"""Digest-bound reading-order sidecar records for COCO layout bundles."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.limits.definition import (
    MAX_COCO_LAYOUT_DETECTIONS,
    MAX_COCO_LAYOUT_IMAGES,
)
from projectkoios.ingestion.integrations.coco.layout.limits.error import (
    CocoLayoutLimitError,
)
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation
from projectkoios.ingestion.sha256.hash import SHA256Hash


@dataclass(frozen=True, slots=True, init=False)
class CocoLayoutAnnotationOrder:
    """Own one complete ordered annotation-ID sequence for an image."""

    _annotation_ids: tuple[int, ...] = field(repr=True)
    order_id: str = field(init=False)

    def __init__(self, *annotation_ids: int) -> None:
        values = tuple(annotation_ids)
        if len(values) > MAX_COCO_LAYOUT_DETECTIONS:
            raise CocoLayoutLimitError(
                "COCO reading order exceeds its implementation limit"
            )
        for value in values:
            if type(value) is not int or value < 0:
                raise ValueError(
                    "ordered annotation IDs must be non-negative integers"
                )
        if len(values) != len(set(values)):
            raise ValueError("ordered annotation IDs must be unique")
        object.__setattr__(self, "_annotation_ids", values)
        object.__setattr__(
            self,
            "order_id",
            stable_id("coco-layout-annotation-order", values),
        )

    def __iter__(self) -> Iterator[int]:
        return iter(self._annotation_ids)

    def __len__(self) -> int:
        return len(self._annotation_ids)


@dataclass(frozen=True, slots=True, init=False)
class CocoLayoutNativeBlockOrder:
    """Own one complete ordered native-block identity sequence."""

    _block_ids: tuple[str, ...] = field(repr=True)
    order_id: str = field(init=False)

    def __init__(self, *block_ids: str) -> None:
        values = tuple(
            LayoutValueValidation.require_text("native block ID", block_id)
            for block_id in block_ids
        )
        if len(values) > MAX_COCO_LAYOUT_DETECTIONS:
            raise CocoLayoutLimitError(
                "native-block reading order exceeds its implementation limit"
            )
        if len(values) != len(set(values)):
            raise ValueError("ordered native block IDs must be unique")
        object.__setattr__(self, "_block_ids", values)
        object.__setattr__(
            self,
            "order_id",
            stable_id("coco-layout-native-block-order", values),
        )

    def __iter__(self) -> Iterator[str]:
        return iter(self._block_ids)

    def __len__(self) -> int:
        return len(self._block_ids)


@dataclass(frozen=True, slots=True)
class CocoLayoutImageReadingOrder(AbstractImmutableDataObject):
    """Bind region and native-block order to one COCO image ID."""

    image_id: int
    annotation_order: CocoLayoutAnnotationOrder
    native_block_order: CocoLayoutNativeBlockOrder
    reading_order_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.image_id) is not int or self.image_id < 0:
            raise ValueError("image_id must be a non-negative integer")
        if type(self.annotation_order) is not CocoLayoutAnnotationOrder:
            raise TypeError(
                "annotation_order must be CocoLayoutAnnotationOrder"
            )
        if type(self.native_block_order) is not CocoLayoutNativeBlockOrder:
            raise TypeError(
                "native_block_order must be CocoLayoutNativeBlockOrder"
            )
        object.__setattr__(
            self,
            "reading_order_id",
            stable_id(
                "coco-layout-image-reading-order",
                self.image_id,
                self.annotation_order.order_id,
                self.native_block_order.order_id,
            ),
        )


@dataclass(frozen=True, slots=True, init=False)
class CocoLayoutImageReadingOrderInventory:
    """Own sorted, unique per-image reading-order records."""

    _orders: tuple[CocoLayoutImageReadingOrder, ...] = field(repr=True)
    inventory_id: str = field(init=False)

    def __init__(self, *orders: CocoLayoutImageReadingOrder) -> None:
        values = tuple(orders)
        if len(values) > MAX_COCO_LAYOUT_IMAGES:
            raise CocoLayoutLimitError(
                "COCO image reading orders exceed their implementation limit"
            )
        if any(
            type(value) is not CocoLayoutImageReadingOrder for value in values
        ):
            raise TypeError("reading-order inventory requires exact records")
        image_ids = tuple(value.image_id for value in values)
        if image_ids != tuple(sorted(image_ids)):
            raise ValueError("reading orders must be sorted by image_id")
        if len(image_ids) != len(set(image_ids)):
            raise ValueError("reading-order image IDs must be unique")
        object.__setattr__(self, "_orders", values)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id(
                "coco-layout-image-reading-order-inventory",
                tuple(value.reading_order_id for value in values),
            ),
        )

    def __iter__(self) -> Iterator[CocoLayoutImageReadingOrder]:
        return iter(self._orders)

    def __len__(self) -> int:
        return len(self._orders)


@dataclass(frozen=True, slots=True)
class CocoLayoutReadingOrderDocument(AbstractImmutableDataObject):
    """Bind reading order to the exact canonical annotations bytes."""

    CONTRACT_NAME: ClassVar[str] = "coco-layout-reading-order-document"
    CONTRACT_VERSION: ClassVar[str] = "0.1"

    annotations_sha256: SHA256Hash
    orders: CocoLayoutImageReadingOrderInventory
    document_id: str = field(init=False)

    def __post_init__(self) -> None:
        digest = SHA256Hash(self.annotations_sha256)
        if type(self.orders) is not CocoLayoutImageReadingOrderInventory:
            raise TypeError(
                "orders must be CocoLayoutImageReadingOrderInventory"
            )
        object.__setattr__(self, "annotations_sha256", digest)
        object.__setattr__(
            self,
            "document_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                digest,
                self.orders.inventory_id,
            ),
        )
