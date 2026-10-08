"""Immutable backend-neutral reading-evidence completion manifests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.storage.transcript.reading.evidence.completion.collection import (  # noqa: E501
    ReadingEvidenceStorageCollectionDigestInventory,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.schema.version import (  # noqa: E501
    ReadingEvidenceStorageSchemaVersion,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)


@dataclass(frozen=True, slots=True)
class ReadingEvidenceCompletionManifest(AbstractImmutableDataObject):
    """Prove one exact backend-neutral generation is complete."""

    CONTRACT_NAME: ClassVar[str] = "reading-evidence-completion-manifest"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    schema_version: ReadingEvidenceStorageSchemaVersion
    generation_id: str
    storage_configuration_id: str
    projection_result_id: ReadingEvidenceIdentity
    evidence_document_id: ReadingEvidenceIdentity
    inventory_id: ReadingEvidenceIdentity
    collections: ReadingEvidenceStorageCollectionDigestInventory
    completion_state: str
    manifest_id: str = field(init=False)
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported completion manifest contract")
        if type(self.schema_version) is not ReadingEvidenceStorageSchemaVersion:
            raise TypeError("schema_version has an unsupported type")
        if type(self.generation_id) is not str or not self.generation_id:
            raise ValueError("generation_id must be non-empty")
        if len(self.generation_id.encode("utf-8", errors="strict")) > 256:
            raise ValueError("generation_id exceeds its limit")
        if (
            type(self.storage_configuration_id) is not str
            or not self.storage_configuration_id
        ):
            raise ValueError("storage_configuration_id must be non-empty")
        if len(self.storage_configuration_id.encode("utf-8")) > 512:
            raise ValueError("storage_configuration_id exceeds its limit")
        self._require_identity(
            self.projection_result_id,
            ReadingEvidenceIdentityKind.PROJECTION_RESULT,
            "projection_result_id",
        )
        self._require_identity(
            self.evidence_document_id,
            ReadingEvidenceIdentityKind.EVIDENCE_DOCUMENT,
            "evidence_document_id",
        )
        self._require_identity(
            self.inventory_id,
            ReadingEvidenceIdentityKind.EVIDENCE_INVENTORY,
            "inventory_id",
        )
        if (
            type(self.collections)
            is not ReadingEvidenceStorageCollectionDigestInventory
        ):
            raise TypeError("collections has an unsupported type")
        if self.completion_state != "complete":
            raise ValueError("completion_state must be complete")
        object.__setattr__(
            self,
            "manifest_id",
            stable_id(
                "reading-evidence-completion-manifest",
                self.CONTRACT_VERSION,
                self.schema_version.schema_id,
                self.generation_id,
                self.storage_configuration_id,
                self.projection_result_id.value,
                self.evidence_document_id.value,
                self.inventory_id.value,
                tuple(value.digest_id for value in self.collections),
                self.completion_state,
            ),
        )

    @staticmethod
    def _require_identity(
        value: object,
        kind: ReadingEvidenceIdentityKind,
        name: str,
    ) -> None:
        if type(value) is not ReadingEvidenceIdentity or value.kind is not kind:
            raise TypeError(f"{name} has the wrong identity role")
