"""Expected full-content inventory derived without querying a target."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import canonical_json, stable_id
from projectkoios.ingestion.storage.extraction.materialization.target import (
    ExtractionProjectionTargetIdentity,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.collection import (  # noqa: E501
    ExtractionProjectionCollectionInventory,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.configuration import (  # noqa: E501
    ExtractionProjectionInventoryConfiguration,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.evidence import (  # noqa: E501
    ExtractionProjectionInventoryEvidence,
)
from projectkoios.ingestion.storage.extraction.projection.read_model import (
    ExtractionReadModel,
)


@dataclass(frozen=True, slots=True)
class ExpectedExtractionProjectionInventory(AbstractImmutableDataObject):
    """Retain expected collection digests without projected document graphs."""

    CONTRACT_NAME: ClassVar[str] = "expected-extraction-projection-inventory"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    expected_inventory_id: str
    target_id: str
    configuration_id: str
    schema_id: str
    canonical_sha256: str
    collections: tuple[ExtractionProjectionCollectionInventory, ...]
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def from_read_models(
        cls,
        *,
        read_models: tuple[ExtractionReadModel, ...],
        target: ExtractionProjectionTargetIdentity,
        configuration: ExtractionProjectionInventoryConfiguration,
    ) -> ExpectedExtractionProjectionInventory:
        """Derive expected inventory from complete immutable read models."""
        if not isinstance(read_models, tuple) or any(
            type(model) is not ExtractionReadModel for model in read_models
        ):
            raise TypeError("expected inventory read models are invalid")
        projection_ids = tuple(model.projection_id for model in read_models)
        if len(projection_ids) != len(set(projection_ids)):
            raise ValueError("expected inventory projections are duplicated")
        if target.schema_id != configuration.schema_id or any(
            model.schema_id != configuration.schema_id for model in read_models
        ):
            raise ValueError("expected inventory schema identities differ")
        members: dict[str, list[tuple[str, str]]] = {
            name: [] for name in configuration.collection_names
        }
        identities: set[tuple[str, str]] = set()
        for model in sorted(read_models, key=lambda item: item.projection_id):
            for document in model.documents:
                collection_name = configuration.collection_name(
                    document.collection
                )
                key = (collection_name, document.document_id)
                if key in identities:
                    raise ValueError(
                        "expected inventory document identity is duplicated"
                    )
                identities.add(key)
                members[collection_name].append(
                    (document.document_id, document.canonical_sha256)
                )
                if (
                    len(members[collection_name])
                    > configuration.maximum_documents_per_collection
                ):
                    raise ValueError("expected inventory exceeds its bound")
        collections = tuple(
            ExtractionProjectionCollectionInventory.create(
                collection_name=name,
                members=tuple(sorted(members[name])),
            )
            for name in configuration.collection_names
        )
        return cls._create(
            target_id=target.target_id,
            configuration_id=configuration.configuration_id,
            schema_id=configuration.schema_id,
            collections=collections,
        )

    @classmethod
    def from_observed(
        cls,
        observed: ExtractionProjectionInventoryEvidence,
    ) -> ExpectedExtractionProjectionInventory:
        """Freeze one observed snapshot as same-store replay expectation."""
        if type(observed) is not ExtractionProjectionInventoryEvidence:
            raise TypeError("observed extraction inventory is invalid")
        return cls._create(
            target_id=observed.target_id,
            configuration_id=observed.configuration_id,
            schema_id=observed.schema_id,
            collections=observed.collections,
        )

    @classmethod
    def _create(
        cls,
        *,
        target_id: str,
        configuration_id: str,
        schema_id: str,
        collections: tuple[ExtractionProjectionCollectionInventory, ...],
    ) -> ExpectedExtractionProjectionInventory:
        values = (
            target_id,
            configuration_id,
            schema_id,
            tuple(item.inventory_id for item in collections),
        )
        digest = hashlib.sha256(
            canonical_json(values).encode("utf-8")
        ).hexdigest()
        return cls(
            expected_inventory_id=stable_id(
                "expected-extraction-projection-inventory",
                cls.CONTRACT_VERSION,
                values,
                digest,
            ),
            target_id=target_id,
            configuration_id=configuration_id,
            schema_id=schema_id,
            canonical_sha256=digest,
            collections=collections,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported expected inventory contract")
        texts = (self.target_id, self.configuration_id, self.schema_id)
        if any(type(value) is not str or not value for value in texts):
            raise ValueError("expected inventory provenance is incomplete")
        if not isinstance(self.collections, tuple) or any(
            type(item) is not ExtractionProjectionCollectionInventory
            for item in self.collections
        ):
            raise TypeError("expected collection inventories are invalid")
        names = tuple(item.collection_name for item in self.collections)
        if names != tuple(sorted(set(names))):
            raise ValueError(
                "expected collection inventories are not canonical"
            )
        values = (*texts, tuple(item.inventory_id for item in self.collections))
        digest = hashlib.sha256(
            canonical_json(values).encode("utf-8")
        ).hexdigest()
        if self.canonical_sha256 != digest:
            raise ValueError("expected inventory digest is inconsistent")
        expected = stable_id(
            "expected-extraction-projection-inventory",
            self.CONTRACT_VERSION,
            values,
            digest,
        )
        if self.expected_inventory_id != expected:
            raise ValueError("expected inventory ID is inconsistent")
