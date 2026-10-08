"""Semantic test owner for current clean-transcript source evidence."""

from __future__ import annotations

from dataclasses import dataclass, replace
from io import BytesIO
from typing import Any

import pytest
from projectkoios.ingestion import (
    DeterministicEquationCandidateDetector,
    DeterministicFigureCandidateDetector,
    DeterministicLayoutProcessor,
    DeterministicTableCandidateDetector,
    PyMuPdfExtractor,
    SourceDocument,
)
from projectkoios.ingestion.articles.structure.actionizer import (
    DeterministicArticleStructureActionizer,
)
from projectkoios.ingestion.articles.structure.request import (
    ArticleStructureRequest,
)
from projectkoios.ingestion.layout import PageLayoutResult
from projectkoios.ingestion.models import ExtractionResult
from projectkoios.ingestion.pdf.adapters.pymupdf.rendering import (
    PyMuPdfRegionRenderer,
)
from projectkoios.ingestion.tables.structure.reconstructor.deterministic import (  # noqa: E501
    DeterministicTableStructureReconstructor,
)
from projectkoios.ingestion.transcription.composer.deterministic import (
    DeterministicStructuredTranscriptionComposer,
)
from projectkoios.ingestion.transcription.request.structured import (
    StructuredTranscriptionRequest,
)
from projectkoios.ingestion.transcription.result.structured import (
    StructuredTranscriptionResult,
)

pymupdf: Any = pytest.importorskip("pymupdf")


@dataclass(frozen=True, slots=True)
class CleanTranscriptSourceFixture:
    """Own one exact current transcription and its source evidence."""

    payload: bytes
    extraction: ExtractionResult
    layouts: tuple[PageLayoutResult, ...]
    transcription: StructuredTranscriptionResult
    private_block_id: str

    @classmethod
    def build(
        cls,
        *,
        replacement_split: str | None = None,
    ) -> CleanTranscriptSourceFixture:
        """Build the deterministic three-page current source fixture."""
        payload = cls.pdf_bytes()
        source = SourceDocument.from_bytes(
            payload,
            source_id="fixture:clean-transcript",
            media_type="application/pdf",
            locator="memory://clean-transcript.pdf",
        )
        extraction = PyMuPdfExtractor().extract(source, BytesIO(payload))
        document = extraction.document
        pages = []
        private_block_id = None
        for page in document.pages:
            blocks = []
            for block in page.blocks:
                if (
                    replacement_split is not None
                    and block.text is not None
                    and "electronic-\nstructure" in block.text
                ):
                    block = replace(block, text=replacement_split)
                if block.text is not None and "private X glyph" in block.text:
                    private_block_id = block.block_id
                    block = replace(
                        block, text=block.text.replace("X", "\ue000")
                    )
                blocks.append(block)
            pages.append(replace(page, blocks=tuple(blocks)))
        assert private_block_id is not None
        document = replace(document, pages=tuple(pages))
        extraction = replace(extraction, document=document)
        layouts = DeterministicLayoutProcessor().analyze(document)
        structure = DeterministicArticleStructureActionizer().action(
            request=ArticleStructureRequest.create(
                document=document,
                layouts=layouts,
            )
        )
        equations = DeterministicEquationCandidateDetector(
            region_renderer=PyMuPdfRegionRenderer()
        ).detect_with_layout(document, BytesIO(payload), layouts)
        table_detection = DeterministicTableCandidateDetector(
            region_renderer=PyMuPdfRegionRenderer(
                max_total_pixels=100_000_000,
                max_total_raster_bytes=100_000_000,
            )
        ).detect_with_layout(document, BytesIO(payload), layouts)
        tables = DeterministicTableStructureReconstructor().reconstruct(
            table_detection
        )
        figures = DeterministicFigureCandidateDetector(
            region_renderer=PyMuPdfRegionRenderer(
                max_total_pixels=100_000_000,
                max_total_raster_bytes=100_000_000,
            )
        ).detect_with_layout(document, BytesIO(payload), layouts)
        transcription = DeterministicStructuredTranscriptionComposer().action(
            request=StructuredTranscriptionRequest.create(
                document=document,
                structure_analysis=structure,
                equation_detection_result=equations,
                table_structure_result=tables,
                figure_detection_result=figures,
            )
        )
        return cls(
            payload=payload,
            extraction=extraction,
            layouts=layouts,
            transcription=transcription,
            private_block_id=private_block_id,
        )

    @classmethod
    def pdf_bytes(cls) -> bytes:
        """Return the deterministic three-page PDF payload."""
        document = pymupdf.open()
        bodies = (
            (
                "electronic-\nstructure remains ambiguous",
                "Copyright 2026 Example Publisher",
                "private X glyph",
                "100",
            ),
            (
                "A tight-binding reference appears here.",
                "The tight-\nbinding model is retained.",
            ),
            (
                "An international reference appears here.",
                "The inter-\nnational result is joined.",
            ),
        )
        for page_index, lines in enumerate(bodies):
            page = document.new_page(width=420, height=420)
            page.insert_text((30, 25), "Repeated Journal Header", fontsize=9)
            for line_index, text in enumerate(lines):
                y0 = 90 + line_index * 55
                page.insert_textbox(
                    (30, y0, 380, y0 + 45),
                    text,
                    fontsize=11,
                )
            page.insert_text((205, 400), str(page_index + 1), fontsize=9)
        payload = document.tobytes()
        document.close()
        return payload
