from __future__ import annotations

from projectkoios.ingestion.base import (
    BasePageLayoutProcessor,
    BaseProcessedDocument,
)
from projectkoios.ingestion.deterministic import DeterministicProcessor
from projectkoios.ingestion.documents.pdf.models import PdfProcessedDocument
from projectkoios.ingestion.layout import DeterministicLayoutProcessor
from projectkoios.ingestion.pilot.models import (
    PilotDeterministicProcessedDocument,
)


class PilotDeterministicProcessor(DeterministicProcessor):
    """Execute the validated extraction-to-layout pilot prefix."""

    name = "pilot-deterministic-processor"
    version = "1"

    def __init__(
        self,
        layout_processor: BasePageLayoutProcessor | None = None,
    ) -> None:
        actual_layout_processor = (
            DeterministicLayoutProcessor()
            if layout_processor is None
            else layout_processor
        )
        if not isinstance(actual_layout_processor, BasePageLayoutProcessor):
            raise TypeError(
                "layout_processor must be a BasePageLayoutProcessor"
            )
        self.layout_processor = actual_layout_processor

    def process(
        self,
        document: BaseProcessedDocument,
    ) -> PilotDeterministicProcessedDocument:
        if not isinstance(document, PdfProcessedDocument):
            raise TypeError(
                "PilotDeterministicProcessor requires PdfProcessedDocument"
            )
        if document.extraction is None:
            raise ValueError(
                "deterministic processing requires retained extraction evidence"
            )
        page_layouts = self.layout_processor.analyze(
            document.extraction.document
        )
        return PilotDeterministicProcessedDocument(
            source=document.source,
            pages=document.pages,
            extraction=document.extraction,
            page_layouts=page_layouts,
        )


__all__ = ["PilotDeterministicProcessor"]
