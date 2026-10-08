"""Cross-component validation for canonical reading evidence documents."""

from __future__ import annotations

from projectkoios.ingestion.artifact.managed.inventory import (
    ManagedArtifactReferenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.block.equation.evidence import (  # noqa: E501
    ReadingEquationEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.block.figure.evidence import (  # noqa: E501
    ReadingFigureEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.block.table.evidence import (  # noqa: E501
    ReadingTableEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.block.text.evidence import (  # noqa: E501
    ReadingTextEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
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
from projectkoios.ingestion.transcript.reading.evidence.lineage.definition import (  # noqa: E501
    ReadingEvidenceLineage,
)
from projectkoios.ingestion.transcript.reading.evidence.page.inventory import (
    ReadingEvidencePageInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.identity import (  # noqa: E501
    ReadingEvidenceProjectionIdentityDerivation,
)


def validate_reading_evidence_document_components(
    *,
    producer_evidence: ReadingDocumentProducerEvidence,
    pages: ReadingEvidencePageInventory,
    retained_figures: ReadingFigureProducerEvidenceInventory,
    retained_tables: ReadingTableProducerEvidenceInventory,
    retained_equations: ReadingEquationProducerEvidenceInventory,
    managed_artifacts: ManagedArtifactReferenceInventory,
    lineage: ReadingEvidenceLineage,
) -> None:
    """Fail closed unless canonical components and lineage agree exactly."""
    if (
        lineage.source_artifact != producer_evidence.source_artifact
        or lineage.extraction_result_id
        != producer_evidence.extraction_result_id
        or lineage.document_producer_id != producer_evidence.record_id
    ):
        raise ReadingEvidenceError(
            "document producer evidence differs from lineage"
        )
    if managed_artifacts != lineage.managed_artifacts:
        raise ReadingEvidenceError("managed artifacts differ from lineage")
    required_artifacts = {
        producer_evidence.source_artifact.artifact_id: (
            producer_evidence.source_artifact
        )
    }
    for producer in (
        *retained_figures,
        *retained_tables,
        *retained_equations,
    ):
        for reference in producer.lineage.artifacts:
            required_artifacts[reference.artifact_id] = reference
    exact_artifacts = ManagedArtifactReferenceInventory(
        *sorted(
            required_artifacts.values(),
            key=lambda value: value.artifact_id,
        )
    )
    if managed_artifacts != exact_artifacts:
        raise ReadingEvidenceError(
            "managed artifacts differ from retained producer evidence"
        )
    blocks = tuple(block for page in pages for block in page.blocks)
    retained_by_block_type = (
        (
            ReadingFigureEvidenceBlock,
            {value.record_id: value for value in retained_figures},
        ),
        (
            ReadingTableEvidenceBlock,
            {value.record_id: value for value in retained_tables},
        ),
        (
            ReadingEquationEvidenceBlock,
            {value.record_id: value for value in retained_equations},
        ),
    )
    for block_type, retained in retained_by_block_type:
        for block in blocks:
            if (
                type(block) is block_type
                and retained.get(block.producer_evidence.record_id)
                != block.producer_evidence
            ):
                raise ReadingEvidenceError(
                    "canonical block producer is absent from retained evidence"
                )
    producer_inventory_inputs = (
        (
            "page_text",
            [page.page_text.record_id.value for page in pages],
            lineage.page_text_inventory_id,
        ),
        (
            "structured_items",
            [block.structured_item.record_id.value for block in blocks],
            lineage.structured_item_inventory_id,
        ),
        (
            "clean_text",
            [
                source.record_id.value
                for block in blocks
                if type(block) is ReadingTextEvidenceBlock
                for source in block.sources
            ],
            lineage.clean_text_inventory_id,
        ),
        (
            "figures",
            retained_figures.identity_material(),
            lineage.figure_inventory_id,
        ),
        (
            "tables",
            retained_tables.identity_material(),
            lineage.table_inventory_id,
        ),
        (
            "equations",
            retained_equations.identity_material(),
            lineage.equation_inventory_id,
        ),
    )
    if any(
        ReadingEvidenceProjectionIdentityDerivation.derive_inventory(
            role=role,
            identities=identities,
        )
        != expected
        for role, identities, expected in producer_inventory_inputs
    ):
        raise ReadingEvidenceError(
            "canonical producer inventories differ from lineage"
        )
