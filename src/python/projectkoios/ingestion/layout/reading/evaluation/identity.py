"""Opaque normalized replica evidence identity inventories."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.identity import stable_id

from .limits import MAX_LAYOUT_READING_ORDER_EVIDENCE_ID_CHARACTERS


@dataclass(frozen=True, slots=True, init=False)
class LayoutReadingOrderReplicaEvidenceIdentityInventory:
    """Own a deterministically ordered set of non-empty opaque identities."""

    _evidence_ids: tuple[str, ...] = field(repr=True)
    inventory_id: str = field(init=False)

    def __init__(self, *evidence_ids: str) -> None:
        values = tuple(evidence_ids)
        if len(values) != len(set(values)):
            raise ValueError("replica evidence identities must be unique")
        if tuple(sorted(values)) != values:
            raise ValueError("replica evidence identities must be sorted")
        for evidence_id in values:
            if not isinstance(evidence_id, str) or not evidence_id.strip():
                raise ValueError(
                    "replica evidence identities must be non-empty"
                )
            if (
                len(evidence_id)
                > MAX_LAYOUT_READING_ORDER_EVIDENCE_ID_CHARACTERS
            ):
                raise ValueError(
                    "replica evidence identity exceeds implementation limit"
                )
            if any(ord(character) < 32 for character in evidence_id):
                raise ValueError(
                    "replica evidence identity contains control characters"
                )
        object.__setattr__(self, "_evidence_ids", values)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id(
                "layout-reading-order-replica-evidence-identity-inventory",
                values,
            ),
        )

    def __iter__(self) -> Iterator[str]:
        return iter(self._evidence_ids)

    def __len__(self) -> int:
        return len(self._evidence_ids)
