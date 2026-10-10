"""Sanitized exact producer bindings for retained text sources."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.page.projection.error import PageProjectionError
from projectkoios.ingestion.page.projection.identity import (
    fingerprint_page_projection_identity,
)
from projectkoios.ingestion.page.projection.limits.definition import (
    PAGE_PROJECTION_LIMITS,
)


@dataclass(frozen=True, slots=True)
class PageProjectionEvidenceProducerBinding:
    """Bind one retained source record to its source block and producer."""

    source_record_id: str
    source_block_id: str
    producer_id: str
    producer_version: str
    binding_id: str = field(init=False)

    def __post_init__(self) -> None:
        source_record_id = PAGE_PROJECTION_LIMITS.require_identity(
            self.source_record_id, "source_record_id"
        )
        source_block_id = PAGE_PROJECTION_LIMITS.require_identity(
            self.source_block_id, "source_block_id"
        )
        producer_id = PAGE_PROJECTION_LIMITS.require_identity(
            self.producer_id, "producer_id"
        )
        producer_version = PAGE_PROJECTION_LIMITS.require_text(
            self.producer_version,
            "producer_version",
            maximum_bytes=PAGE_PROJECTION_LIMITS.maximum_processor_version_bytes,
        )
        object.__setattr__(
            self,
            "binding_id",
            fingerprint_page_projection_identity(
                namespace="page-projection-evidence-producer-binding",
                material={
                    "producer_id": producer_id,
                    "producer_version": producer_version,
                    "source_block_id": source_block_id,
                    "source_record_id": source_record_id,
                },
            ),
        )


@dataclass(frozen=True, slots=True, init=False)
class PageProjectionEvidenceProducerBindingInventory:
    """Own declared retained-source order without losing producer alignment."""

    _bindings: tuple[PageProjectionEvidenceProducerBinding, ...] = field(
        repr=True
    )
    inventory_id: str = field(init=False)

    def __init__(
        self,
        *bindings: PageProjectionEvidenceProducerBinding,
    ) -> None:
        values = tuple(bindings)
        PAGE_PROJECTION_LIMITS.require_count(
            len(values),
            "producer binding count",
            maximum=PAGE_PROJECTION_LIMITS.maximum_enrichment_identities,
        )
        if not values:
            raise PageProjectionError(
                "retained text requires producer bindings"
            )
        if any(
            type(value) is not PageProjectionEvidenceProducerBinding
            for value in values
        ):
            raise TypeError(
                "producer binding inventory contains an invalid value"
            )
        record_ids = tuple(value.source_record_id for value in values)
        source_block_ids = tuple(value.source_block_id for value in values)
        if len(record_ids) != len(set(record_ids)) or len(
            source_block_ids
        ) != len(set(source_block_ids)):
            raise PageProjectionError(
                "producer bindings require unique source records and blocks"
            )
        object.__setattr__(self, "_bindings", values)
        object.__setattr__(
            self,
            "inventory_id",
            fingerprint_page_projection_identity(
                namespace="page-projection-evidence-producer-inventory",
                material={
                    "binding_ids": [value.binding_id for value in values]
                },
            ),
        )

    def __iter__(self) -> Iterator[PageProjectionEvidenceProducerBinding]:
        return iter(self._bindings)

    def __len__(self) -> int:
        return len(self._bindings)
