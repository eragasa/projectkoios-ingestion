"""Query-only actionizer for extraction projection inventories."""

from __future__ import annotations

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.storage.extraction.actions.disposition import (
    ExtractionActionDisposition,
)
from projectkoios.ingestion.storage.extraction.projection_inventory.reader import (  # noqa: E501
    ExtractionProjectionInventoryReader,
)
from projectkoios.ingestion.storage.extraction.projection_inventory.reader_error import (  # noqa: E501
    ExtractionProjectionInventoryReaderError,
)
from projectkoios.ingestion.storage.extraction.projection_inventory.request import (  # noqa: E501
    ExtractionProjectionInventoryRequest,
)
from projectkoios.ingestion.storage.extraction.projection_inventory.result import (  # noqa: E501
    ExtractionProjectionInventoryResult,
)


class ExtractionProjectionInventoryActionizer(
    DataObjectActionizer[
        ExtractionProjectionInventoryRequest,
        ExtractionProjectionInventoryResult,
    ]
):
    """Return compact, deterministic evidence for every owned collection."""

    __slots__ = ("reader",)

    actionizer_name = "extraction-projection-inventory"
    actionizer_version = "1"
    collection_names = (
        "extraction_blocks",
        "extraction_documents",
        "extraction_manifests",
        "extraction_pages",
        "extraction_warnings",
    )

    def __init__(self, *, reader: ExtractionProjectionInventoryReader) -> None:
        if not isinstance(reader, ExtractionProjectionInventoryReader):
            raise TypeError(
                "reader must be an ExtractionProjectionInventoryReader"
            )
        self.reader = reader

    def action(
        self,
        *,
        request: ExtractionProjectionInventoryRequest,
    ) -> ExtractionProjectionInventoryResult:
        if not isinstance(request, ExtractionProjectionInventoryRequest):
            raise TypeError(
                "request must be an ExtractionProjectionInventoryRequest"
            )
        try:
            collections = self.reader.read_inventory(
                projection_reference=request.projection_reference,
                authority_id=request.authority_id,
            )
        except ExtractionProjectionInventoryReaderError as error:
            return ExtractionProjectionInventoryResult.failed(
                request=request,
                disposition=error.disposition,
                failure_code=error.code,
                actionizer_name=self.actionizer_name,
                actionizer_version=self.actionizer_version,
            )
        names = tuple(item.collection_name for item in collections)
        if names != self.collection_names:
            return ExtractionProjectionInventoryResult.failed(
                request=request,
                disposition=(
                    ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
                ),
                failure_code="projection_collection_set_differs",
                actionizer_name=self.actionizer_name,
                actionizer_version=self.actionizer_version,
            )
        return ExtractionProjectionInventoryResult.completed(
            request=request,
            collections=collections,
            actionizer_name=self.actionizer_name,
            actionizer_version=self.actionizer_version,
        )
