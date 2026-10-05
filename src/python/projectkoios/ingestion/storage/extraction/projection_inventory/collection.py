"""Compact deterministic inventory for one extraction projection collection."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id

_SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class ExtractionProjectionCollectionInventory(AbstractImmutableDataObject):
    """Count and privacy-safe digests without retaining projection documents."""

    CONTRACT_VERSION: ClassVar[str] = "1.0"
    MAXIMUM_DOCUMENTS: ClassVar[int] = 50_000_000

    inventory_id: str
    collection_name: str
    document_count: int
    identity_sha256: str
    publication_sha256: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        collection_name: str,
        members: tuple[tuple[str, str], ...],
    ) -> ExtractionProjectionCollectionInventory:
        if not isinstance(members, tuple) or any(
            not isinstance(member, tuple)
            or len(member) != 2
            or type(member[0]) is not str
            or not member[0]
            or type(member[1]) is not str
            or not _SHA256.fullmatch(member[1])
            for member in members
        ):
            raise TypeError("projection inventory members are invalid")
        if len(members) > cls.MAXIMUM_DOCUMENTS:
            raise ValueError("projection inventory exceeds its limit")
        if members != tuple(sorted(members)):
            raise ValueError("projection inventory members must be sorted")
        identities = tuple(identity for identity, _ in members)
        if len(identities) != len(set(identities)):
            raise ValueError("projection inventory identities must be unique")
        identity_sha256 = cls._digest(identities)
        publication_sha256 = cls._digest(members)
        return cls(
            inventory_id=stable_id(
                "extraction-projection-collection-inventory",
                cls.CONTRACT_VERSION,
                collection_name,
                len(members),
                identity_sha256,
                publication_sha256,
            ),
            collection_name=collection_name,
            document_count=len(members),
            identity_sha256=identity_sha256,
            publication_sha256=publication_sha256,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported collection-inventory contract")
        if (
            type(self.collection_name) is not str
            or not self.collection_name
            or len(self.collection_name) > 256
        ):
            raise ValueError("projection collection name is invalid")
        if (
            isinstance(self.document_count, bool)
            or not isinstance(self.document_count, int)
            or not 0 <= self.document_count <= self.MAXIMUM_DOCUMENTS
        ):
            raise ValueError("projection document count is out of bounds")
        for value in (self.identity_sha256, self.publication_sha256):
            if type(value) is not str or not _SHA256.fullmatch(value):
                raise ValueError("projection inventory digest is invalid")
        expected = stable_id(
            "extraction-projection-collection-inventory",
            self.CONTRACT_VERSION,
            self.collection_name,
            self.document_count,
            self.identity_sha256,
            self.publication_sha256,
        )
        if self.inventory_id != expected:
            raise ValueError("collection-inventory ID is inconsistent")

    @staticmethod
    def _digest(value: object) -> str:
        serialized = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(serialized).hexdigest()
