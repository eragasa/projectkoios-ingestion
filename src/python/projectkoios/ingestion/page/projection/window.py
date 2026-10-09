"""Bounded grouping views over projected page inventories."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.page.projection.error import PageProjectionError
from projectkoios.ingestion.page.projection.identity import (
    PageProjectionResultIdentityDerivation,
)
from projectkoios.ingestion.page.projection.limits.definition import (
    PAGE_PROJECTION_LIMITS,
)
from projectkoios.ingestion.page.projection.page import (
    PageProjectionPageInventory,
)


@dataclass(frozen=True, slots=True, init=False)
class PageProjectionPageWindowInventory:
    """Group exact pages without altering their identities or order."""

    source_inventory_id: str
    window_size: int
    _windows: tuple[PageProjectionPageInventory, ...] = field(repr=True)
    inventory_id: str = field(init=False)

    def __init__(
        self,
        *,
        pages: PageProjectionPageInventory,
        window_size: int,
    ) -> None:
        if type(pages) is not PageProjectionPageInventory:
            raise TypeError("pages must be PageProjectionPageInventory")
        if type(window_size) is not int or not (
            1 <= window_size <= PAGE_PROJECTION_LIMITS.maximum_pages
        ):
            raise PageProjectionError("window_size is outside its bounds")
        page_values = tuple(pages)
        windows = tuple(
            PageProjectionPageInventory(
                *page_values[offset : offset + window_size]
            )
            for offset in range(0, len(page_values), window_size)
        )
        object.__setattr__(self, "source_inventory_id", pages.inventory_id)
        object.__setattr__(self, "window_size", window_size)
        object.__setattr__(self, "_windows", windows)
        object.__setattr__(
            self,
            "inventory_id",
            PageProjectionResultIdentityDerivation.derive_window_inventory(
                source_inventory_id=pages.inventory_id,
                window_size=window_size,
                window_inventory_ids=tuple(
                    value.inventory_id for value in windows
                ),
            ),
        )

    def __iter__(self) -> Iterator[PageProjectionPageInventory]:
        return iter(self._windows)

    def __len__(self) -> int:
        return len(self._windows)
