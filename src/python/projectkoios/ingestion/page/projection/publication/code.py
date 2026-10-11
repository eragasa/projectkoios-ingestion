"""Bounded immutable safe code inventory for publication receipts."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import cast

from projectkoios.ingestion.json.value import JsonValue
from projectkoios.ingestion.page.projection.limits.definition import (
    PAGE_PROJECTION_LIMITS,
)


@dataclass(frozen=True, slots=True, init=False)
class PageProjectionPublicationCodeInventory:
    """Own sorted unique warning or limitation codes."""

    _codes: tuple[str, ...] = field(repr=True)

    def __init__(self, *codes: str) -> None:
        values = tuple(codes)
        if len(values) > PAGE_PROJECTION_LIMITS.maximum_blocks:
            raise ValueError("publication code count exceeds its limit")
        validated = tuple(
            PAGE_PROJECTION_LIMITS.require_identity(value, "publication code")
            for value in values
        )
        if validated != tuple(sorted(set(validated))):
            raise ValueError("publication codes must be sorted and unique")
        object.__setattr__(self, "_codes", validated)

    def __iter__(self) -> Iterator[str]:
        return iter(self._codes)

    def __len__(self) -> int:
        return len(self._codes)

    def values(self) -> list[JsonValue]:
        """Return ephemeral canonical JSON material."""
        return cast(list[JsonValue], list(self._codes))
