"""Locator-free COCO image identity bound to exact page renders."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.limits.definition import (
    MAX_COCO_LAYOUT_IMAGES,
)
from projectkoios.ingestion.integrations.coco.layout.limits.error import (
    CocoLayoutLimitError,
)
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation
from projectkoios.ingestion.sha256.hash import SHA256Hash


@dataclass(frozen=True, slots=True)
class CocoLayoutImage(AbstractImmutableDataObject):
    """Bind one integer COCO image ID to an exact managed render identity."""

    image_id: int
    render_id: str
    width: int
    height: int
    image_media_type: str
    image_sha256: SHA256Hash
    image_identity: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            isinstance(self.image_id, bool)
            or not isinstance(self.image_id, int)
            or self.image_id < 0
        ):
            raise ValueError("image_id must be a non-negative integer")
        render = LayoutValueValidation.require_text("render_id", self.render_id)
        width = LayoutValueValidation.require_positive_integer(
            "width", self.width
        )
        height = LayoutValueValidation.require_positive_integer(
            "height", self.height
        )
        media_type = LayoutValueValidation.require_text(
            "image_media_type", self.image_media_type
        )
        if media_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise ValueError("unsupported COCO bundle image media type")
        digest = SHA256Hash(self.image_sha256)
        object.__setattr__(self, "image_sha256", digest)
        object.__setattr__(
            self,
            "image_identity",
            stable_id(
                "coco-layout-image",
                self.image_id,
                render,
                width,
                height,
                media_type,
                digest,
            ),
        )

    @property
    def bundle_file_name(self) -> str:
        """Return one safe deterministic bundle-local image filename."""
        extension = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
        }[self.image_media_type]
        return f"images/{self.image_id:08d}.{extension}"


@dataclass(frozen=True, slots=True, init=False)
class CocoLayoutImageInventory:
    """Own one ordered, unique, bounded COCO image collection."""

    _images: tuple[CocoLayoutImage, ...] = field(repr=True)
    inventory_id: str = field(init=False)

    def __init__(self, *images: CocoLayoutImage) -> None:
        values = tuple(images)
        if not values:
            raise ValueError("COCO image inventory must be non-empty")
        if len(values) > MAX_COCO_LAYOUT_IMAGES:
            raise CocoLayoutLimitError(
                "COCO images exceed their implementation limit"
            )
        if any(type(value) is not CocoLayoutImage for value in values):
            raise TypeError("COCO image inventory requires exact images")
        ids = tuple(value.image_id for value in values)
        if ids != tuple(sorted(ids)):
            raise ValueError("COCO images must be sorted by image_id")
        if len(ids) != len(set(ids)):
            raise ValueError("COCO image IDs must be unique")
        renders = tuple(value.render_id for value in values)
        if len(renders) != len(set(renders)):
            raise ValueError("COCO render IDs must be unique")
        object.__setattr__(self, "_images", values)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id(
                "coco-layout-image-inventory",
                tuple(value.image_identity for value in values),
            ),
        )

    def __iter__(self) -> Iterator[CocoLayoutImage]:
        return iter(self._images)

    def __len__(self) -> int:
        return len(self._images)

    def require(self, image_id: int) -> CocoLayoutImage:
        """Return one exact image or reject an unknown integer ID."""
        for image in self._images:
            if image.image_id == image_id:
                return image
        raise ValueError("COCO annotation references an unknown image")
