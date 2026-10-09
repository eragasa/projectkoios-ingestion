"""Immutable manifest records for Koios COCO layout bundles."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.limits.definition import (
    MAX_COCO_LAYOUT_JSON_BYTES,
)
from projectkoios.ingestion.integrations.coco.layout.limits.error import (
    CocoLayoutLimitError,
)
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.hash import SHA256Hash


class CocoLayoutBundleMemberName(StrEnum):
    """Declare the complete non-manifest member registry for profile v0.1."""

    ANNOTATIONS = "annotations.coco.json"
    LINEAGE = "lineage.json"
    READING_ORDER = "reading-order.json"


@dataclass(frozen=True, slots=True)
class CocoLayoutBundleMember(AbstractImmutableDataObject):
    """Bind one semantic document to exact canonical bundle-member bytes."""

    name: CocoLayoutBundleMemberName
    document_id: str
    sha256: SHA256Hash
    byte_length: int
    media_type: str = "application/json"
    member_id: str = field(init=False)

    @classmethod
    def create(
        cls,
        *,
        name: CocoLayoutBundleMemberName,
        document_id: str,
        content: bytes,
    ) -> CocoLayoutBundleMember:
        """Create one exact bounded member reference from canonical bytes."""
        if type(content) is not bytes:
            raise TypeError("content must be bytes")
        if len(content) > MAX_COCO_LAYOUT_JSON_BYTES:
            raise CocoLayoutLimitError("COCO bundle member exceeds byte limit")
        return cls(
            name=name,
            document_id=document_id,
            sha256=SHA256Fingerprinter.fingerprint(content=content),
            byte_length=len(content),
        )

    def __post_init__(self) -> None:
        if not isinstance(self.name, CocoLayoutBundleMemberName):
            raise TypeError("name must be CocoLayoutBundleMemberName")
        document = LayoutValueValidation.require_text(
            "document_id", self.document_id
        )
        digest = SHA256Hash(self.sha256)
        length = LayoutValueValidation.require_positive_integer(
            "byte_length", self.byte_length
        )
        if length > MAX_COCO_LAYOUT_JSON_BYTES:
            raise CocoLayoutLimitError("COCO bundle member exceeds byte limit")
        media_type = LayoutValueValidation.require_text(
            "media_type", self.media_type
        )
        if media_type != "application/json":
            raise ValueError("COCO bundle members must use application/json")
        object.__setattr__(self, "sha256", digest)
        object.__setattr__(
            self,
            "member_id",
            stable_id(
                "coco-layout-bundle-member",
                self.name,
                document,
                digest,
                length,
                media_type,
            ),
        )


@dataclass(frozen=True, slots=True, init=False)
class CocoLayoutBundleMemberInventory:
    """Own the exact, complete, canonically ordered v0.1 member set."""

    _members: tuple[CocoLayoutBundleMember, ...] = field(repr=True)
    inventory_id: str = field(init=False)

    def __init__(self, *members: CocoLayoutBundleMember) -> None:
        values = tuple(members)
        if any(type(value) is not CocoLayoutBundleMember for value in values):
            raise TypeError("bundle member inventory requires exact members")
        names = tuple(value.name for value in values)
        expected = tuple(sorted(CocoLayoutBundleMemberName, key=str))
        if names != expected:
            raise ValueError(
                "COCO bundle members must be complete and sorted by name"
            )
        object.__setattr__(self, "_members", values)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id(
                "coco-layout-bundle-member-inventory",
                tuple(value.member_id for value in values),
            ),
        )

    def __iter__(self) -> Iterator[CocoLayoutBundleMember]:
        return iter(self._members)

    def __len__(self) -> int:
        return len(self._members)

    def require(
        self, name: CocoLayoutBundleMemberName
    ) -> CocoLayoutBundleMember:
        """Return one exact member by its fixed role."""
        for member in self._members:
            if member.name is name:
                return member
        raise ValueError("COCO bundle member is absent")


@dataclass(frozen=True, slots=True)
class CocoLayoutBundleManifest(AbstractImmutableDataObject):
    """Bind profile identity to every non-manifest bundle member."""

    CONTRACT_NAME: ClassVar[str] = "coco-layout-bundle-manifest"
    CONTRACT_VERSION: ClassVar[str] = "0.1"

    profile_id: str
    members: CocoLayoutBundleMemberInventory
    manifest_id: str = field(init=False)

    def __post_init__(self) -> None:
        profile = LayoutValueValidation.require_text(
            "profile_id", self.profile_id
        )
        if type(self.members) is not CocoLayoutBundleMemberInventory:
            raise TypeError("members must be CocoLayoutBundleMemberInventory")
        object.__setattr__(
            self,
            "manifest_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                profile,
                self.members.inventory_id,
            ),
        )
