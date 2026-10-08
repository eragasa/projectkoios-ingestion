"""Canonical backend-neutral reading evidence documents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.artifact.managed.inventory import (
    ManagedArtifactReferenceInventory,
)
from projectkoios.ingestion.sha256.hash import SHA256Hash
from projectkoios.ingestion.transcript.reading.evidence.document.validation import (  # noqa: E501
    validate_reading_evidence_document_components,
)
from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
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
from projectkoios.ingestion.transcript.reading.evidence.input.table.inventory import (  # noqa: E501
    ReadingTableProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.limitation.inventory import (  # noqa: E501
    ReadingEvidenceLimitationInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.lineage.definition import (  # noqa: E501
    ReadingEvidenceLineage,
)
from projectkoios.ingestion.transcript.reading.evidence.page.inventory import (
    ReadingEvidencePageInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.identity import (  # noqa: E501
    ReadingEvidenceProjectionIdentityDerivation,
)


@dataclass(frozen=True, slots=True)
class ReadingEvidenceDocument:
    """Own one complete immutable backend-neutral reading evidence aggregate."""

    CONTRACT_VERSION: ClassVar[str] = "projectkoios-reading-evidence-v1"

    producer_evidence: ReadingDocumentProducerEvidence
    pages: ReadingEvidencePageInventory
    retained_figures: ReadingFigureProducerEvidenceInventory
    retained_tables: ReadingTableProducerEvidenceInventory
    retained_equations: ReadingEquationProducerEvidenceInventory
    managed_artifacts: ManagedArtifactReferenceInventory
    lineage: ReadingEvidenceLineage
    limitations: ReadingEvidenceLimitationInventory
    contract_version: str = CONTRACT_VERSION
    document_id: ReadingEvidenceIdentity = field(init=False)

    def __post_init__(self) -> None:
        if type(self.producer_evidence) is not ReadingDocumentProducerEvidence:
            raise TypeError("producer_evidence has an unsupported type")
        if type(self.pages) is not ReadingEvidencePageInventory:
            raise TypeError("pages must be ReadingEvidencePageInventory")
        if len(self.pages) != self.producer_evidence.expected_page_count:
            raise ReadingEvidenceError(
                "document page count differs from producer evidence"
            )
        if (
            type(self.retained_figures)
            is not ReadingFigureProducerEvidenceInventory
        ):
            raise TypeError("retained_figures has an unsupported type")
        if (
            type(self.retained_tables)
            is not ReadingTableProducerEvidenceInventory
        ):
            raise TypeError("retained_tables has an unsupported type")
        if (
            type(self.retained_equations)
            is not ReadingEquationProducerEvidenceInventory
        ):
            raise TypeError("retained_equations has an unsupported type")
        if (
            type(self.managed_artifacts)
            is not ManagedArtifactReferenceInventory
        ):
            raise TypeError("managed_artifacts has an unsupported type")
        if type(self.lineage) is not ReadingEvidenceLineage:
            raise TypeError("lineage must be ReadingEvidenceLineage")
        if type(self.limitations) is not ReadingEvidenceLimitationInventory:
            raise TypeError("limitations has an unsupported type")
        if self.contract_version != self.CONTRACT_VERSION:
            raise ReadingEvidenceError(
                "unsupported reading evidence contract version"
            )
        validate_reading_evidence_document_components(
            producer_evidence=self.producer_evidence,
            pages=self.pages,
            retained_figures=self.retained_figures,
            retained_tables=self.retained_tables,
            retained_equations=self.retained_equations,
            managed_artifacts=self.managed_artifacts,
            lineage=self.lineage,
        )
        page_inventory_id = (
            ReadingEvidenceProjectionIdentityDerivation.derive_inventory(
                role="canonical_pages",
                identities=self.pages.identity_material(),
            )
        )
        limitation_inventory_id = (
            ReadingEvidenceProjectionIdentityDerivation.derive_inventory(
                role="limitations",
                identities=self.limitations.identity_material(),
            )
        )
        object.__setattr__(
            self,
            "document_id",
            ReadingEvidenceProjectionIdentityDerivation.derive_document(
                source_document_id=self.producer_evidence.document_id,
                page_inventory_id=page_inventory_id,
                lineage_id=self.lineage.lineage_id,
                limitation_inventory_id=limitation_inventory_id,
                contract_version=self.contract_version,
            ),
        )

    @property
    def source_id(self) -> ReadingEvidenceIdentity:
        """Return the exact source identity."""
        return self.producer_evidence.source_id

    @property
    def source_sha256(self) -> SHA256Hash:
        """Return the exact source artifact SHA-256."""
        return self.producer_evidence.source_sha256
