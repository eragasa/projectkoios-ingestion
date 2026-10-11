"""Exact typed upstream limitations applicable to enriched evidence."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum

from projectkoios.ingestion.page.projection.enrichment.identity import (
    PageProjectionEvidenceAffectedIdentityInventory,
)
from projectkoios.ingestion.page.projection.error import PageProjectionError
from projectkoios.ingestion.page.projection.identity import (
    fingerprint_page_projection_identity,
)
from projectkoios.ingestion.page.projection.limits.definition import (
    PAGE_PROJECTION_LIMITS,
)


class PageProjectionEvidenceLimitationCode(StrEnum):
    """Mirror only exact current canonical reading limitation codes."""

    UNREVIEWED_VISUAL_EVIDENCE = "unreviewed_visual_evidence"
    UNACCEPTED_EQUATION_EVIDENCE = "unaccepted_equation_evidence"
    MISSING_OPTIONAL_RECOGNITION = "missing_optional_recognition"
    INVALID_GEOMETRY_OMITTED = "invalid_geometry_omitted"
    UNPLACED_PRODUCER_EVIDENCE = "unplaced_producer_evidence"


@dataclass(frozen=True, slots=True)
class PageProjectionEvidenceLimitation:
    """Retain one exact limitation identity, code, and affected identities."""

    limitation_id: str
    code: PageProjectionEvidenceLimitationCode
    affected_ids: PageProjectionEvidenceAffectedIdentityInventory
    record_id: str = field(init=False)

    def __post_init__(self) -> None:
        limitation_id = PAGE_PROJECTION_LIMITS.require_identity(
            self.limitation_id, "limitation_id"
        )
        if not isinstance(self.code, PageProjectionEvidenceLimitationCode):
            raise TypeError("limitation code has an unsupported type")
        if (
            type(self.affected_ids)
            is not PageProjectionEvidenceAffectedIdentityInventory
            or not self.affected_ids
        ):
            raise PageProjectionError(
                "limitation requires exact affected identities"
            )
        object.__setattr__(
            self,
            "record_id",
            fingerprint_page_projection_identity(
                namespace="page-projection-evidence-limitation",
                material={
                    "affected_ids": self.affected_ids.identity_material(),
                    "code": self.code.value,
                    "limitation_id": limitation_id,
                },
            ),
        )


@dataclass(frozen=True, slots=True, init=False)
class PageProjectionEvidenceLimitationInventory:
    """Own one limitation-ID-ordered unique exact limitation collection."""

    _limitations: tuple[PageProjectionEvidenceLimitation, ...] = field(
        repr=True
    )
    inventory_id: str = field(init=False)

    def __init__(
        self,
        *limitations: PageProjectionEvidenceLimitation,
    ) -> None:
        values = tuple(limitations)
        PAGE_PROJECTION_LIMITS.require_count(
            len(values),
            "enrichment limitation count",
            maximum=PAGE_PROJECTION_LIMITS.maximum_enrichment_limitations,
        )
        if any(
            type(value) is not PageProjectionEvidenceLimitation
            for value in values
        ):
            raise TypeError("limitation inventory contains an invalid value")
        ids = tuple(value.limitation_id for value in values)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise PageProjectionError(
                "enrichment limitations must be ID ordered and unique"
            )
        object.__setattr__(self, "_limitations", values)
        object.__setattr__(
            self,
            "inventory_id",
            fingerprint_page_projection_identity(
                namespace="page-projection-evidence-limitation-inventory",
                material={
                    "limitation_record_ids": [
                        value.record_id for value in values
                    ]
                },
            ),
        )

    def __bool__(self) -> bool:
        return bool(self._limitations)

    def __iter__(self) -> Iterator[PageProjectionEvidenceLimitation]:
        return iter(self._limitations)

    def __len__(self) -> int:
        return len(self._limitations)
