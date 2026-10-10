"""Ordered complete inventories of enrichment entries."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.page.projection.enrichment.record import (
    PageProjectionEvidenceEnrichment,
    PageProjectionEvidenceEntry,
    PageProjectionEvidenceUnavailable,
)
from projectkoios.ingestion.page.projection.error import PageProjectionError
from projectkoios.ingestion.page.projection.identity import (
    fingerprint_page_projection_identity,
)
from projectkoios.ingestion.page.projection.limits.definition import (
    PAGE_PROJECTION_LIMITS,
)

_ENTRY_TYPES = (
    PageProjectionEvidenceEnrichment,
    PageProjectionEvidenceUnavailable,
)


@dataclass(frozen=True, slots=True, init=False)
class PageProjectionEvidenceEnrichmentInventory:
    """Own one exact projected-block-ordered enrichment disposition per key."""

    _entries: tuple[PageProjectionEvidenceEntry, ...] = field(repr=True)
    available_count: int
    unavailable_count: int
    inventory_id: str = field(init=False)

    def __init__(self, *entries: PageProjectionEvidenceEntry) -> None:
        values = tuple(entries)
        PAGE_PROJECTION_LIMITS.require_count(
            len(values),
            "enrichment entry count",
            maximum=PAGE_PROJECTION_LIMITS.maximum_blocks,
        )
        if any(type(value) not in _ENTRY_TYPES for value in values):
            raise TypeError("enrichment inventory contains an invalid value")
        evidence_ids = tuple(value.source_evidence_id for value in values)
        block_ids = tuple(value.page_projection_block_id for value in values)
        if len(evidence_ids) != len(set(evidence_ids)):
            raise PageProjectionError(
                "enrichment source-evidence identities must be unique"
            )
        if len(block_ids) != len(set(block_ids)):
            raise PageProjectionError(
                "enrichment projected-block identities must be unique"
            )
        page_order: list[str] = []
        entry_ids_by_page: dict[str, list[str]] = {}
        for value in values:
            page_id = value.page_projection_page_id
            if page_id not in entry_ids_by_page:
                page_order.append(page_id)
                entry_ids_by_page[page_id] = []
            elif page_order[-1] != page_id:
                raise PageProjectionError(
                    "enrichment entries must be contiguous by projected page"
                )
            entry_ids_by_page[page_id].append(value.entry_id)
        page_manifest_ids = [
            fingerprint_page_projection_identity(
                namespace="page-projection-evidence-page-manifest",
                material={
                    "entry_ids": entry_ids_by_page[page_id],
                    "page_projection_page_id": page_id,
                },
            )
            for page_id in page_order
        ]
        available_count = sum(
            type(value) is PageProjectionEvidenceEnrichment for value in values
        )
        object.__setattr__(self, "_entries", values)
        object.__setattr__(self, "available_count", available_count)
        object.__setattr__(
            self,
            "unavailable_count",
            len(values) - available_count,
        )
        object.__setattr__(
            self,
            "inventory_id",
            fingerprint_page_projection_identity(
                namespace="page-projection-evidence-enrichment-inventory",
                material={"page_manifest_ids": page_manifest_ids},
            ),
        )

    def __bool__(self) -> bool:
        return bool(self._entries)

    def __iter__(self) -> Iterator[PageProjectionEvidenceEntry]:
        return iter(self._entries)

    def __len__(self) -> int:
        return len(self._entries)
