"""Exact aggregate lineage for canonical reading evidence."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.artifact.managed.inventory import (
    ManagedArtifactReferenceInventory,
)
from projectkoios.ingestion.artifact.managed.reference import (
    ManagedArtifactReference,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.derivation import (  # noqa: E501
    ReadingEvidenceIdentityDerivation,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)


@dataclass(frozen=True, slots=True)
class ReadingEvidenceLineage:
    """Bind every exact producer aggregate and artifact inventory used."""

    source_artifact: ManagedArtifactReference
    extraction_result_id: ReadingEvidenceIdentity
    document_producer_id: ReadingEvidenceIdentity
    page_text_inventory_id: ReadingEvidenceIdentity
    structured_item_inventory_id: ReadingEvidenceIdentity
    clean_text_inventory_id: ReadingEvidenceIdentity
    figure_inventory_id: ReadingEvidenceIdentity
    table_inventory_id: ReadingEvidenceIdentity
    equation_inventory_id: ReadingEvidenceIdentity
    projection_configuration_id: ReadingEvidenceIdentity
    managed_artifacts: ManagedArtifactReferenceInventory
    lineage_id: ReadingEvidenceIdentity = field(init=False)

    def __post_init__(self) -> None:
        if type(self.source_artifact) is not ManagedArtifactReference:
            raise TypeError("source_artifact must be ManagedArtifactReference")
        if (
            type(self.extraction_result_id) is not ReadingEvidenceIdentity
            or self.extraction_result_id.kind
            is not ReadingEvidenceIdentityKind.EXTRACTION_RESULT
        ):
            raise TypeError("extraction_result_id has the wrong identity role")
        if (
            type(self.document_producer_id) is not ReadingEvidenceIdentity
            or self.document_producer_id.kind
            is not ReadingEvidenceIdentityKind.DOCUMENT_PRODUCER
        ):
            raise TypeError("document_producer_id has the wrong identity role")
        inventories = (
            self.page_text_inventory_id,
            self.structured_item_inventory_id,
            self.clean_text_inventory_id,
            self.figure_inventory_id,
            self.table_inventory_id,
            self.equation_inventory_id,
        )
        if any(
            type(value) is not ReadingEvidenceIdentity
            or value.kind is not ReadingEvidenceIdentityKind.EVIDENCE_INVENTORY
            for value in inventories
        ):
            raise TypeError("producer inventory identity has the wrong role")
        if (
            type(self.projection_configuration_id)
            is not ReadingEvidenceIdentity
            or self.projection_configuration_id.kind
            is not ReadingEvidenceIdentityKind.PROJECTION_CONFIGURATION
        ):
            raise TypeError("projection_configuration_id has the wrong role")
        if (
            type(self.managed_artifacts)
            is not ManagedArtifactReferenceInventory
        ):
            raise TypeError("managed_artifacts has an unsupported type")
        if (
            self.managed_artifacts.require(self.source_artifact.artifact_id)
            != self.source_artifact
        ):
            raise ValueError("source artifact is absent from managed artifacts")
        object.__setattr__(
            self,
            "lineage_id",
            ReadingEvidenceIdentityDerivation.derive(
                kind=ReadingEvidenceIdentityKind.LINEAGE,
                prefix="reading-evidence-lineage",
                material={
                    "source_artifact_id": self.source_artifact.artifact_id,
                    "extraction_result_id": self.extraction_result_id.value,
                    "document_producer_id": self.document_producer_id.value,
                    "producer_inventory_ids": [
                        value.value for value in inventories
                    ],
                    "projection_configuration_id": (
                        self.projection_configuration_id.value
                    ),
                    "managed_artifact_ids": [
                        value.artifact_id for value in self.managed_artifacts
                    ],
                },
            ),
        )
