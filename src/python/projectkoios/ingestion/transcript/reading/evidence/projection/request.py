"""Immutable bounded requests for pure canonical reading projection."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.artifact.managed.inventory import (
    ManagedArtifactReferenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.input.document import (
    ReadingDocumentProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.equation.inventory import (  # noqa: E501
    ReadingEquationProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.figure.inventory import (  # noqa: E501
    ReadingFigureProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.page.inventory import (  # noqa: E501
    ReadingPageTextProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.inventory import (  # noqa: E501
    ReadingStructuredItemProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.table.inventory import (  # noqa: E501
    ReadingTableProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.inventory import (  # noqa: E501
    ReadingCleanTextProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.inventory.expected import (  # noqa: E501
    ExpectedReadingEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    ReadingEvidenceLimits,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.configuration import (  # noqa: E501
    ReadingEvidenceProjectionConfiguration,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.identity import (  # noqa: E501
    ReadingEvidenceProjectionIdentityDerivation,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.validation import (  # noqa: E501
    validate_reading_evidence_projection_inputs,
)


@dataclass(frozen=True, slots=True)
class ReadingEvidenceProjectionRequest(DataObjectActionRequest):
    """Bind every exact producer input required for one pure projection."""

    document: ReadingDocumentProducerEvidence
    page_text: ReadingPageTextProducerEvidenceInventory
    structured_items: ReadingStructuredItemProducerEvidenceInventory
    clean_text: ReadingCleanTextProducerEvidenceInventory
    figures: ReadingFigureProducerEvidenceInventory
    tables: ReadingTableProducerEvidenceInventory
    equations: ReadingEquationProducerEvidenceInventory
    managed_artifacts: ManagedArtifactReferenceInventory
    expected_inventory: ExpectedReadingEvidenceInventory
    configuration: ReadingEvidenceProjectionConfiguration
    limits: ReadingEvidenceLimits
    page_text_inventory_id: ReadingEvidenceIdentity = field(init=False)
    structured_item_inventory_id: ReadingEvidenceIdentity = field(init=False)
    clean_text_inventory_id: ReadingEvidenceIdentity = field(init=False)
    figure_inventory_id: ReadingEvidenceIdentity = field(init=False)
    table_inventory_id: ReadingEvidenceIdentity = field(init=False)
    equation_inventory_id: ReadingEvidenceIdentity = field(init=False)
    managed_inventory_id: ReadingEvidenceIdentity = field(init=False)
    request_id: ReadingEvidenceIdentity = field(init=False)

    def __post_init__(self) -> None:
        validate_reading_evidence_projection_inputs(
            document=self.document,
            page_text=self.page_text,
            structured_items=self.structured_items,
            clean_text=self.clean_text,
            figures=self.figures,
            tables=self.tables,
            equations=self.equations,
            managed_artifacts=self.managed_artifacts,
            expected_inventory=self.expected_inventory,
            configuration=self.configuration,
            limits=self.limits,
        )
        inventory_values = (
            (
                "page_text",
                [value.record_id.value for value in self.page_text],
                "page_text_inventory_id",
            ),
            (
                "structured_items",
                [value.record_id.value for value in self.structured_items],
                "structured_item_inventory_id",
            ),
            (
                "clean_text",
                [value.record_id.value for value in self.clean_text],
                "clean_text_inventory_id",
            ),
            (
                "figures",
                [value.record_id.value for value in self.figures],
                "figure_inventory_id",
            ),
            (
                "tables",
                [value.record_id.value for value in self.tables],
                "table_inventory_id",
            ),
            (
                "equations",
                [value.record_id.value for value in self.equations],
                "equation_inventory_id",
            ),
            (
                "managed_artifacts",
                [value.artifact_id for value in self.managed_artifacts],
                "managed_inventory_id",
            ),
        )
        derived: list[ReadingEvidenceIdentity] = []
        for role, identities, field_name in inventory_values:
            identity = (
                ReadingEvidenceProjectionIdentityDerivation.derive_inventory(
                    role=role,
                    identities=identities,
                )
            )
            object.__setattr__(self, field_name, identity)
            derived.append(identity)
        object.__setattr__(
            self,
            "request_id",
            ReadingEvidenceProjectionIdentityDerivation.derive_request(
                document_producer_id=self.document.record_id,
                producer_inventory_ids=derived[:-1],
                managed_inventory_id=self.managed_inventory_id,
                expected_inventory_id=self.expected_inventory.expectation_id,
                configuration_id=self.configuration.configuration_id,
            ),
        )
