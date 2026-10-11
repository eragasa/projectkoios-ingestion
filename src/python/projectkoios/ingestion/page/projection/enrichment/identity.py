"""Bounded immutable identity collections for enrichment records."""

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


@dataclass(frozen=True, slots=True, init=False)
class PageProjectionEvidenceIdentityInventory:
    """Own one declared-order unique collection of opaque identities."""

    _identities: tuple[str, ...] = field(repr=True)
    inventory_id: str = field(init=False)

    def __init__(self, *identities: str) -> None:
        values = tuple(
            PAGE_PROJECTION_LIMITS.require_identity(value, "evidence identity")
            for value in identities
        )
        PAGE_PROJECTION_LIMITS.require_count(
            len(values),
            "evidence identity count",
            maximum=(PAGE_PROJECTION_LIMITS.maximum_enrichment_identities),
        )
        if len(values) != len(set(values)):
            raise PageProjectionError("evidence identities must be unique")
        object.__setattr__(self, "_identities", values)
        object.__setattr__(
            self,
            "inventory_id",
            fingerprint_page_projection_identity(
                namespace="page-projection-evidence-identity-inventory",
                material={"identities": list(values)},
            ),
        )

    def __bool__(self) -> bool:
        return bool(self._identities)

    def __iter__(self) -> Iterator[str]:
        return iter(self._identities)

    def __len__(self) -> int:
        return len(self._identities)

    def identity_material(self) -> list[str]:
        """Return ephemeral ordered identity material."""
        return list(self._identities)


@dataclass(frozen=True, slots=True)
class PageProjectionEvidenceAffectedIdentity:
    """Retain one exact typed upstream limitation target."""

    kind: str
    value: str
    reference_id: str = field(init=False)

    def __post_init__(self) -> None:
        kind = PAGE_PROJECTION_LIMITS.require_text(
            self.kind,
            "affected identity kind",
            maximum_bytes=(
                PAGE_PROJECTION_LIMITS.maximum_enrichment_code_bytes
            ),
        )
        value = PAGE_PROJECTION_LIMITS.require_identity(
            self.value, "affected identity value"
        )
        object.__setattr__(
            self,
            "reference_id",
            fingerprint_page_projection_identity(
                namespace="page-projection-evidence-affected-identity",
                material={"kind": kind, "value": value},
            ),
        )


@dataclass(frozen=True, slots=True, init=False)
class PageProjectionEvidenceAffectedIdentityInventory:
    """Own one exact ordered unique typed affected-identity collection."""

    _references: tuple[PageProjectionEvidenceAffectedIdentity, ...] = field(
        repr=True
    )
    inventory_id: str = field(init=False)

    def __init__(
        self,
        *references: PageProjectionEvidenceAffectedIdentity,
    ) -> None:
        values = tuple(references)
        PAGE_PROJECTION_LIMITS.require_count(
            len(values),
            "affected identity count",
            maximum=(PAGE_PROJECTION_LIMITS.maximum_enrichment_identities),
        )
        if any(
            type(value) is not PageProjectionEvidenceAffectedIdentity
            for value in values
        ):
            raise TypeError(
                "affected identity inventory contains an invalid value"
            )
        keys = tuple((value.kind, value.value) for value in values)
        if len(keys) != len(set(keys)):
            raise PageProjectionError(
                "affected identity references must be unique"
            )
        object.__setattr__(self, "_references", values)
        object.__setattr__(
            self,
            "inventory_id",
            fingerprint_page_projection_identity(
                namespace=(
                    "page-projection-evidence-affected-identity-inventory"
                ),
                material={
                    "references": [
                        {"kind": value.kind, "value": value.value}
                        for value in values
                    ]
                },
            ),
        )

    def __bool__(self) -> bool:
        return bool(self._references)

    def __iter__(self) -> Iterator[PageProjectionEvidenceAffectedIdentity]:
        return iter(self._references)

    def __len__(self) -> int:
        return len(self._references)

    def identity_material(self) -> list[dict[str, str]]:
        """Return ephemeral exact typed identity material."""
        return [
            {"kind": value.kind, "value": value.value}
            for value in self._references
        ]
