"""Complete observed evidence for one extraction projection target."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.projector.inventory.evidence import (
    AbstractProjectorInventoryEvidence,
)
from projectkoios.ingestion.identity import canonical_json, stable_id
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.storage.extraction.projection.inventory.collection import (  # noqa: E501
    ExtractionProjectionCollectionInventory,
)


@dataclass(frozen=True, slots=True)
class ExtractionProjectionInventoryEvidence(AbstractProjectorInventoryEvidence):
    """Bind full-content collection digests to target and query provenance."""

    CONTRACT_NAME: ClassVar[str] = "extraction-projection-inventory-evidence"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    inventory_id: str
    target_id: str
    configuration_id: str
    authority_id: str
    canonical_sha256: str
    schema_id: str
    collections: tuple[ExtractionProjectionCollectionInventory, ...]
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        target_id: str,
        configuration_id: str,
        authority_id: str,
        schema_id: str,
        collections: tuple[ExtractionProjectionCollectionInventory, ...],
    ) -> ExtractionProjectionInventoryEvidence:
        """Create aggregate evidence from canonical collection inventories."""
        values = (
            target_id,
            configuration_id,
            authority_id,
            schema_id,
            tuple(item.inventory_id for item in collections),
        )
        digest = SHA256Fingerprinter.fingerprint(
            content=canonical_json(values).encode("utf-8")
        )
        return cls(
            inventory_id=stable_id(
                "extraction-projection-inventory-evidence",
                cls.CONTRACT_VERSION,
                values,
                digest,
            ),
            target_id=target_id,
            configuration_id=configuration_id,
            authority_id=authority_id,
            canonical_sha256=digest,
            schema_id=schema_id,
            collections=collections,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported extraction inventory evidence")
        texts = (
            self.target_id,
            self.configuration_id,
            self.authority_id,
            self.schema_id,
        )
        if any(type(value) is not str or not value for value in texts):
            raise ValueError("extraction inventory provenance is incomplete")
        if not isinstance(self.collections, tuple) or any(
            type(item) is not ExtractionProjectionCollectionInventory
            for item in self.collections
        ):
            raise TypeError("extraction collection inventories are invalid")
        names = tuple(item.collection_name for item in self.collections)
        if names != tuple(sorted(set(names))):
            raise ValueError(
                "extraction collection inventories are not canonical"
            )
        values = (
            *texts,
            tuple(item.inventory_id for item in self.collections),
        )
        digest = SHA256Fingerprinter.fingerprint(
            content=canonical_json(values).encode("utf-8")
        )
        if self.canonical_sha256 != digest:
            raise ValueError("extraction inventory digest is inconsistent")
        expected = stable_id(
            "extraction-projection-inventory-evidence",
            self.CONTRACT_VERSION,
            values,
            digest,
        )
        if self.inventory_id != expected:
            raise ValueError("extraction inventory ID is inconsistent")
