"""Versioned Koios COCO layout interchange profiles."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.category import (
    CocoLayoutCategoryInventory,
)
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation


@dataclass(frozen=True, slots=True)
class CocoLayoutProfile(AbstractImmutableDataObject):
    """Pin category and coordinate semantics independently of any detector."""

    CONTRACT_NAME: ClassVar[str] = "coco-layout-profile"
    CONTRACT_VERSION: ClassVar[str] = "1.0"
    XYWH_COORDINATE_CONVENTION: ClassVar[str] = (
        "top-left-origin-render-pixels-xywh"
    )
    KOIOS_PROFILE_NAME: ClassVar[str] = "koios-coco-layout-profile"
    KOIOS_PROFILE_VERSION: ClassVar[str] = "0.1"

    name: str
    version: str
    categories: CocoLayoutCategoryInventory
    profile_id: str = field(init=False)

    def __post_init__(self) -> None:
        name = LayoutValueValidation.require_text("name", self.name)
        version = LayoutValueValidation.require_text("version", self.version)
        if type(self.categories) is not CocoLayoutCategoryInventory:
            raise TypeError("categories must be CocoLayoutCategoryInventory")
        if name == self.KOIOS_PROFILE_NAME:
            if version != self.KOIOS_PROFILE_VERSION:
                raise ValueError(
                    "unsupported Koios COCO Layout Profile version"
                )
            if self.categories != CocoLayoutCategoryInventory.doclaynet_v1():
                raise ValueError(
                    "Koios COCO Layout Profile v0.1 categories differ"
                )
        object.__setattr__(
            self,
            "profile_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                name,
                version,
                self.XYWH_COORDINATE_CONVENTION,
                self.categories.inventory_id,
            ),
        )

    @classmethod
    def koios_doclaynet_v0_1(cls) -> CocoLayoutProfile:
        """Return Koios COCO Layout Profile v0.1 with DocLayNet categories."""
        return cls(
            name=cls.KOIOS_PROFILE_NAME,
            version=cls.KOIOS_PROFILE_VERSION,
            categories=CocoLayoutCategoryInventory.doclaynet_v1(),
        )
