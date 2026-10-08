"""Pure synchronous canonical reading evidence projection action."""

from __future__ import annotations

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.transcript.reading.evidence.document.definition import (  # noqa: E501
    ReadingEvidenceDocument,
)
from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.inventory.definition import (  # noqa: E501
    ReadingEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.lineage.definition import (  # noqa: E501
    ReadingEvidenceLineage,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.limitation import (  # noqa: E501
    derive_reading_evidence_limitations,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.page import (  # noqa: E501
    project_reading_evidence_pages,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.request import (  # noqa: E501
    ReadingEvidenceProjectionRequest,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.result import (  # noqa: E501
    ReadingEvidenceProjectionResult,
)
from projectkoios.ingestion.transcript.reading.evidence.reconciliation.definition import (  # noqa: E501
    ReadingEvidenceReconciliation,
)


class ReadingEvidenceProjectionActionizer(
    DataObjectActionizer[
        ReadingEvidenceProjectionRequest,
        ReadingEvidenceProjectionResult,
    ]
):
    """Join exact producer evidence into one complete canonical document."""

    __slots__ = ()

    PROCESSOR_NAME = "projectkoios-reading-evidence-projector"
    PROCESSOR_VERSION = "1"

    def action(
        self,
        *,
        request: ReadingEvidenceProjectionRequest,
    ) -> ReadingEvidenceProjectionResult:
        """Project one bounded request without I/O or lifecycle behavior."""
        if type(request) is not ReadingEvidenceProjectionRequest:
            raise TypeError("request must be ReadingEvidenceProjectionRequest")
        page_projection = project_reading_evidence_pages(request=request)
        limitations = derive_reading_evidence_limitations(
            request=request,
            page_projection=page_projection,
        )
        lineage = ReadingEvidenceLineage(
            source_artifact=request.document.source_artifact,
            extraction_result_id=request.document.extraction_result_id,
            document_producer_id=request.document.record_id,
            page_text_inventory_id=request.page_text_inventory_id,
            structured_item_inventory_id=(request.structured_item_inventory_id),
            clean_text_inventory_id=request.clean_text_inventory_id,
            figure_inventory_id=request.figure_inventory_id,
            table_inventory_id=request.table_inventory_id,
            equation_inventory_id=request.equation_inventory_id,
            projection_configuration_id=(
                request.configuration.configuration_id
            ),
            managed_artifacts=request.managed_artifacts,
        )
        document = ReadingEvidenceDocument(
            producer_evidence=request.document,
            pages=page_projection.pages,
            retained_figures=request.figures,
            retained_tables=request.tables,
            retained_equations=request.equations,
            managed_artifacts=request.managed_artifacts,
            lineage=lineage,
            limitations=limitations,
        )
        inventory = ReadingEvidenceInventory.observe(document)
        reconciliation = ReadingEvidenceReconciliation(
            expected=request.expected_inventory,
            observed=inventory,
        )
        if not reconciliation.complete:
            mismatch_names = ", ".join(
                value.value for value in reconciliation.mismatches
            )
            raise ReadingEvidenceError(
                f"reading evidence reconciliation failed: {mismatch_names}"
            )
        return ReadingEvidenceProjectionResult(
            request=request,
            document=document,
            inventory=inventory,
            reconciliation=reconciliation,
            processor_id=ReadingEvidenceIdentity(
                kind=ReadingEvidenceIdentityKind.PRODUCER,
                value=self.PROCESSOR_NAME,
            ),
            processor_version=self.PROCESSOR_VERSION,
            limitations=limitations,
        )
