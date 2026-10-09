"""Digest-bound proposal lineage sidecar records for COCO layout bundles."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.limits.definition import (
    MAX_COCO_LAYOUT_DETECTIONS,
)
from projectkoios.ingestion.integrations.coco.layout.limits.error import (
    CocoLayoutLimitError,
)
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation
from projectkoios.ingestion.sha256.hash import SHA256Hash


@dataclass(frozen=True, slots=True, init=False)
class CocoLayoutNativeBlockIdentityInventory:
    """Own one sorted, unique native-block membership set."""

    _block_ids: tuple[str, ...] = field(repr=True)
    inventory_id: str = field(init=False)

    def __init__(self, *block_ids: str) -> None:
        values = tuple(
            LayoutValueValidation.require_text("native block ID", block_id)
            for block_id in block_ids
        )
        if len(values) > MAX_COCO_LAYOUT_DETECTIONS:
            raise CocoLayoutLimitError(
                "native block memberships exceed their implementation limit"
            )
        if values != tuple(sorted(values)):
            raise ValueError("native block IDs must be sorted")
        if len(values) != len(set(values)):
            raise ValueError("native block IDs must be unique")
        object.__setattr__(self, "_block_ids", values)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id("coco-layout-native-block-inventory", values),
        )

    def __iter__(self) -> Iterator[str]:
        return iter(self._block_ids)

    def __len__(self) -> int:
        return len(self._block_ids)


class CocoLayoutNativeBlockMembershipStatus(StrEnum):
    """Distinguish absent evaluation from evaluated empty membership."""

    NOT_EVALUATED = "not_evaluated"
    EVALUATED = "evaluated"


@dataclass(frozen=True, slots=True)
class CocoLayoutAnnotationNativeBlockMembership(AbstractImmutableDataObject):
    """Bind one COCO annotation to exact native block identities."""

    annotation_id: int
    status: CocoLayoutNativeBlockMembershipStatus
    block_ids: CocoLayoutNativeBlockIdentityInventory
    membership_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.annotation_id) is not int or self.annotation_id < 0:
            raise ValueError("annotation_id must be a non-negative integer")
        if not isinstance(self.status, CocoLayoutNativeBlockMembershipStatus):
            raise TypeError(
                "status must be CocoLayoutNativeBlockMembershipStatus"
            )
        if type(self.block_ids) is not CocoLayoutNativeBlockIdentityInventory:
            raise TypeError(
                "block_ids must be CocoLayoutNativeBlockIdentityInventory"
            )
        if (
            self.status is CocoLayoutNativeBlockMembershipStatus.NOT_EVALUATED
            and self.block_ids
        ):
            raise ValueError(
                "not-evaluated membership cannot identify native blocks"
            )
        object.__setattr__(
            self,
            "membership_id",
            stable_id(
                "coco-layout-annotation-native-block-membership",
                self.annotation_id,
                self.status,
                self.block_ids.inventory_id,
            ),
        )


@dataclass(frozen=True, slots=True, init=False)
class CocoLayoutAnnotationNativeBlockMembershipInventory:
    """Own exact native-block membership for every annotation."""

    _memberships: tuple[CocoLayoutAnnotationNativeBlockMembership, ...] = field(
        repr=True
    )
    inventory_id: str = field(init=False)

    def __init__(
        self, *memberships: CocoLayoutAnnotationNativeBlockMembership
    ) -> None:
        values = tuple(memberships)
        if len(values) > MAX_COCO_LAYOUT_DETECTIONS:
            raise CocoLayoutLimitError(
                "annotation memberships exceed their implementation limit"
            )
        if any(
            type(value) is not CocoLayoutAnnotationNativeBlockMembership
            for value in values
        ):
            raise TypeError("membership inventory requires exact memberships")
        annotation_ids = tuple(value.annotation_id for value in values)
        if annotation_ids != tuple(sorted(annotation_ids)):
            raise ValueError("memberships must be sorted by annotation_id")
        if len(annotation_ids) != len(set(annotation_ids)):
            raise ValueError("membership annotation IDs must be unique")
        object.__setattr__(self, "_memberships", values)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id(
                "coco-layout-annotation-membership-inventory",
                tuple(value.membership_id for value in values),
            ),
        )

    def __iter__(self) -> Iterator[CocoLayoutAnnotationNativeBlockMembership]:
        return iter(self._memberships)

    def require(
        self, annotation_id: int
    ) -> CocoLayoutAnnotationNativeBlockMembership:
        """Return exact native-block membership for one annotation."""
        for membership in self._memberships:
            if membership.annotation_id == annotation_id:
                return membership
        raise ValueError("native-block membership is absent")


@dataclass(frozen=True, slots=True)
class CocoLayoutAnnotationLineage(AbstractImmutableDataObject):
    """Bind one annotation to its derivation and native-block membership."""

    annotation_id: int
    detection_id: str
    proposal_id: str
    adaptation_id: str
    native_block_membership_status: CocoLayoutNativeBlockMembershipStatus
    native_block_ids: CocoLayoutNativeBlockIdentityInventory
    lineage_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.annotation_id) is not int or self.annotation_id < 0:
            raise ValueError("annotation_id must be a non-negative integer")
        values = tuple(
            LayoutValueValidation.require_text(name, getattr(self, name))
            for name in ("detection_id", "proposal_id", "adaptation_id")
        )
        if not isinstance(
            self.native_block_membership_status,
            CocoLayoutNativeBlockMembershipStatus,
        ):
            raise TypeError(
                "native_block_membership_status must use the status enum"
            )
        if type(self.native_block_ids) is not (
            CocoLayoutNativeBlockIdentityInventory
        ):
            raise TypeError(
                "native_block_ids must use the exact identity inventory"
            )
        object.__setattr__(
            self,
            "lineage_id",
            stable_id(
                "coco-layout-annotation-lineage",
                self.annotation_id,
                values,
                self.native_block_membership_status,
                self.native_block_ids.inventory_id,
            ),
        )


@dataclass(frozen=True, slots=True, init=False)
class CocoLayoutAnnotationLineageInventory:
    """Own sorted, unique annotation derivation lineage."""

    _entries: tuple[CocoLayoutAnnotationLineage, ...] = field(repr=True)
    inventory_id: str = field(init=False)

    def __init__(self, *entries: CocoLayoutAnnotationLineage) -> None:
        values = tuple(entries)
        if len(values) > MAX_COCO_LAYOUT_DETECTIONS:
            raise CocoLayoutLimitError(
                "COCO lineage entries exceed their implementation limit"
            )
        if any(
            type(value) is not CocoLayoutAnnotationLineage for value in values
        ):
            raise TypeError("lineage inventory requires exact entries")
        annotation_ids = tuple(value.annotation_id for value in values)
        if annotation_ids != tuple(sorted(annotation_ids)):
            raise ValueError("lineage entries must be sorted by annotation_id")
        if len(annotation_ids) != len(set(annotation_ids)):
            raise ValueError("lineage annotation IDs must be unique")
        object.__setattr__(self, "_entries", values)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id(
                "coco-layout-annotation-lineage-inventory",
                tuple(value.lineage_id for value in values),
            ),
        )

    def __iter__(self) -> Iterator[CocoLayoutAnnotationLineage]:
        return iter(self._entries)

    def __len__(self) -> int:
        return len(self._entries)


@dataclass(frozen=True, slots=True)
class CocoLayoutLineageDocument(AbstractImmutableDataObject):
    """Bind exact proposal lineage to canonical annotations bytes."""

    CONTRACT_NAME: ClassVar[str] = "coco-layout-lineage-document"
    CONTRACT_VERSION: ClassVar[str] = "0.1"

    annotations_sha256: SHA256Hash
    profile_id: str
    configuration_id: str
    proposal_source_id: str
    entries: CocoLayoutAnnotationLineageInventory
    document_id: str = field(init=False)

    def __post_init__(self) -> None:
        digest = SHA256Hash(self.annotations_sha256)
        values = tuple(
            LayoutValueValidation.require_text(name, getattr(self, name))
            for name in (
                "profile_id",
                "configuration_id",
                "proposal_source_id",
            )
        )
        if type(self.entries) is not CocoLayoutAnnotationLineageInventory:
            raise TypeError(
                "entries must be CocoLayoutAnnotationLineageInventory"
            )
        object.__setattr__(self, "annotations_sha256", digest)
        object.__setattr__(
            self,
            "document_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                digest,
                values,
                self.entries.inventory_id,
            ),
        )
