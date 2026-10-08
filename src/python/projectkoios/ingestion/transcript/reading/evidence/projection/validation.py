"""Exact bounded input validation for canonical reading projection."""

from __future__ import annotations

from projectkoios.ingestion.artifact.managed.inventory import (
    ManagedArtifactReferenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.input.document import (
    ReadingDocumentProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.equation.evidence import (  # noqa: E501
    ReadingEquationProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.equation.inventory import (  # noqa: E501
    ReadingEquationProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.figure.evidence import (  # noqa: E501
    ReadingFigureProducerEvidence,
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
from projectkoios.ingestion.transcript.reading.evidence.input.table.evidence import (  # noqa: E501
    ReadingTableProducerEvidence,
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


def validate_reading_evidence_projection_inputs(
    *,
    document: ReadingDocumentProducerEvidence,
    page_text: ReadingPageTextProducerEvidenceInventory,
    structured_items: ReadingStructuredItemProducerEvidenceInventory,
    clean_text: ReadingCleanTextProducerEvidenceInventory,
    figures: ReadingFigureProducerEvidenceInventory,
    tables: ReadingTableProducerEvidenceInventory,
    equations: ReadingEquationProducerEvidenceInventory,
    managed_artifacts: ManagedArtifactReferenceInventory,
    expected_inventory: ExpectedReadingEvidenceInventory,
    configuration: ReadingEvidenceProjectionConfiguration,
    limits: ReadingEvidenceLimits,
) -> None:
    """Fail closed unless every projection input and exact join is valid."""
    types = (
        (document, ReadingDocumentProducerEvidence, "document"),
        (page_text, ReadingPageTextProducerEvidenceInventory, "page_text"),
        (
            structured_items,
            ReadingStructuredItemProducerEvidenceInventory,
            "structured_items",
        ),
        (clean_text, ReadingCleanTextProducerEvidenceInventory, "clean_text"),
        (figures, ReadingFigureProducerEvidenceInventory, "figures"),
        (tables, ReadingTableProducerEvidenceInventory, "tables"),
        (equations, ReadingEquationProducerEvidenceInventory, "equations"),
        (
            managed_artifacts,
            ManagedArtifactReferenceInventory,
            "managed_artifacts",
        ),
        (
            expected_inventory,
            ExpectedReadingEvidenceInventory,
            "expected_inventory",
        ),
        (
            configuration,
            ReadingEvidenceProjectionConfiguration,
            "configuration",
        ),
        (limits, ReadingEvidenceLimits, "limits"),
    )
    for field_value, expected_type, name in types:
        if type(field_value) is not expected_type:
            raise TypeError(f"{name} has an unsupported type")
    if limits != configuration.limits:
        raise ReadingEvidenceError("request and configuration limits differ")
    if len(page_text) != document.expected_page_count:
        raise ReadingEvidenceError("document and page-text coverage differ")
    managed_artifacts.require(document.source_artifact.artifact_id)
    selected_stream_by_page = {
        value.streams.page_location: value.selection.selected_stream_id
        for value in page_text
    }
    page_locations = set(selected_stream_by_page)
    if any(
        value.page_location not in page_locations for value in structured_items
    ) or any(value.page_location not in page_locations for value in clean_text):
        raise ReadingEvidenceError("text producer binds an unknown page")
    if any(
        value.selected_stream_id != selected_stream_by_page[value.page_location]
        for value in clean_text
    ):
        raise ReadingEvidenceError(
            "clean-text evidence differs from the selected page stream"
        )
    source_id = document.source_id
    producer_values: list[
        ReadingFigureProducerEvidence
        | ReadingTableProducerEvidence
        | ReadingEquationProducerEvidence
    ] = [*figures, *tables, *equations]
    if any(
        value.lineage.page_location not in page_locations
        or any(
            span.source_id != source_id for span in value.lineage.source_spans
        )
        for value in producer_values
    ) or any(
        any(span.source_id != source_id for span in value.source_spans)
        for value in clean_text
    ):
        raise ReadingEvidenceError(
            "producer source lineage differs from document"
        )
    clean_block_ids = {value.source_block_id for value in clean_text}
    visual_values: list[
        ReadingFigureProducerEvidence | ReadingTableProducerEvidence
    ] = [*figures, *tables]
    for visual_value in visual_values:
        for association in visual_value.assessment.associations:
            if any(
                source_block_id not in clean_block_ids
                for source_block_id in association.source_block_ids
            ) or any(
                span.source_id != source_id
                or span.page_location != visual_value.lineage.page_location
                for span in association.source_spans
            ):
                raise ReadingEvidenceError(
                    "visual association lineage differs from text evidence"
                )
    object_ids = tuple(
        value.lineage.source_object_id.value for value in producer_values
    )
    if len(object_ids) != len(set(object_ids)):
        raise ReadingEvidenceError(
            "producer source objects must be globally unique"
        )
    required_artifacts = {
        document.source_artifact.artifact_id: document.source_artifact
    }
    for producer_value in producer_values:
        for reference in producer_value.lineage.artifacts:
            if managed_artifacts.require(reference.artifact_id) != reference:
                raise ReadingEvidenceError(
                    "producer artifact reference differs"
                )
            required_artifacts[reference.artifact_id] = reference
    exact_artifacts = ManagedArtifactReferenceInventory(
        *sorted(
            required_artifacts.values(),
            key=lambda value: value.artifact_id,
        )
    )
    if managed_artifacts != exact_artifacts:
        raise ReadingEvidenceError(
            "managed artifacts differ from referenced producer artifacts"
        )
    work = (
        len(page_text)
        + len(structured_items)
        + len(clean_text)
        + len(figures)
        + len(tables)
        + len(equations)
    )
    if work > limits.maximum_total_projection_work:
        raise ReadingEvidenceError("projection work exceeds its limit")
