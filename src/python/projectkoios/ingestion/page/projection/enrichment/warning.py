"""Exact upstream warning identities without invented producer detail."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.page.projection.enrichment.basis import (
    PageProjectionEvidenceWarningDetailStatus,
)
from projectkoios.ingestion.page.projection.enrichment.identity import (
    PageProjectionEvidenceIdentityInventory,
)
from projectkoios.ingestion.page.projection.error import PageProjectionError
from projectkoios.ingestion.page.projection.identity import (
    fingerprint_page_projection_identity,
)
from projectkoios.ingestion.page.projection.limits.definition import (
    PAGE_PROJECTION_LIMITS,
)


@dataclass(frozen=True, slots=True)
class PageProjectionEvidenceWarning:
    """Retain one opaque producer warning and its exact affected evidence."""

    warning_id: str
    affected_ids: PageProjectionEvidenceIdentityInventory
    detail_status: PageProjectionEvidenceWarningDetailStatus
    detail: str | None
    record_id: str = field(init=False)

    def __post_init__(self) -> None:
        warning_id = PAGE_PROJECTION_LIMITS.require_identity(
            self.warning_id, "warning_id"
        )
        if (
            type(self.affected_ids)
            is not PageProjectionEvidenceIdentityInventory
        ):
            raise TypeError(
                "affected_ids must be PageProjectionEvidenceIdentityInventory"
            )
        if not self.affected_ids:
            raise PageProjectionError("warning requires affected identities")
        if not isinstance(
            self.detail_status,
            PageProjectionEvidenceWarningDetailStatus,
        ):
            raise TypeError("detail_status has an unsupported type")
        if (
            self.detail_status
            is PageProjectionEvidenceWarningDetailStatus.UNAVAILABLE
        ):
            if self.detail is not None:
                raise PageProjectionError(
                    "unavailable warning detail must be absent"
                )
        else:
            PAGE_PROJECTION_LIMITS.require_text(
                self.detail,
                "warning detail",
                maximum_bytes=(
                    PAGE_PROJECTION_LIMITS.maximum_enrichment_detail_bytes
                ),
            )
        object.__setattr__(
            self,
            "record_id",
            fingerprint_page_projection_identity(
                namespace="page-projection-evidence-warning",
                material={
                    "affected_ids": self.affected_ids.identity_material(),
                    "detail": self.detail,
                    "detail_status": self.detail_status.value,
                    "warning_id": warning_id,
                },
            ),
        )


@dataclass(frozen=True, slots=True, init=False)
class PageProjectionEvidenceWarningInventory:
    """Own one warning-ID-ordered unique exact warning collection."""

    _warnings: tuple[PageProjectionEvidenceWarning, ...] = field(repr=True)
    inventory_id: str = field(init=False)

    def __init__(self, *warnings: PageProjectionEvidenceWarning) -> None:
        values = tuple(warnings)
        PAGE_PROJECTION_LIMITS.require_count(
            len(values),
            "enrichment warning count",
            maximum=PAGE_PROJECTION_LIMITS.maximum_enrichment_warnings,
        )
        if any(
            type(value) is not PageProjectionEvidenceWarning for value in values
        ):
            raise TypeError("warning inventory contains an invalid value")
        ids = tuple(value.warning_id for value in values)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise PageProjectionError(
                "enrichment warnings must be warning-ID ordered and unique"
            )
        object.__setattr__(self, "_warnings", values)
        object.__setattr__(
            self,
            "inventory_id",
            fingerprint_page_projection_identity(
                namespace="page-projection-evidence-warning-inventory",
                material={
                    "warning_record_ids": [value.record_id for value in values]
                },
            ),
        )

    def __bool__(self) -> bool:
        return bool(self._warnings)

    def __iter__(self) -> Iterator[PageProjectionEvidenceWarning]:
        return iter(self._warnings)

    def __len__(self) -> int:
        return len(self._warnings)
