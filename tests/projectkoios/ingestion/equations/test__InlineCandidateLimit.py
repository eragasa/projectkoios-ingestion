from __future__ import annotations

from io import BytesIO
from typing import BinaryIO

from projectkoios.ingestion.equations import (
    DeterministicEquationCandidateDetector,
)
from projectkoios.ingestion.models import (
    ExtractedBlock,
    ExtractedDocument,
    ExtractedPage,
    SourceDocument,
    SourceSpan,
    WarningSeverity,
)
from projectkoios.ingestion.pdf.models import (
    PYMUPDF_COORDINATE_SYSTEM,
    PageRegionSelection,
    RenderedRegion,
)
from projectkoios.ingestion.pdf.renderer import PageRegionRenderer

_PRESSURE_LIST = """Al
As (P =14 GPa)
Ba (P =20 GPa)
Be
Bi (P =8 GPa)
Cd
Ce (P =5 GPa)
Cs(P=13GPa)
Ga
Hf
Hg
In
Ir
La
Lu
Mg
Mo
Nb
P(P=17GPa)
Pb
Ru
Se (P =13 GPa)
Si (P =12 GPa)
Sn
Ta
Tc
Te (P = 8 GPa)
Th
Ti
Tl
U
W
Y (P =17 GPa)
Zn
Zr"""


class _UnexpectedRenderer(PageRegionRenderer):
    name = "unexpected-test-renderer"
    version = "1"

    def render(
        self,
        source: SourceDocument,
        content: BinaryIO,
        selections: tuple[PageRegionSelection, ...],
    ) -> tuple[RenderedRegion, ...]:
        del source, content, selections
        raise AssertionError("candidate-limit prose must not be rendered")


def _document() -> tuple[bytes, ExtractedDocument, ExtractedBlock]:
    payload = b"%PDF-1.7\nawkward inline-candidate fixture\n%%EOF\n"
    source = SourceDocument.from_bytes(
        payload,
        source_id="article:marder-pressure-list",
        media_type="application/pdf",
        locator="memory://marder-pressure-list.pdf",
    )
    block = ExtractedBlock.create(
        kind="text",
        source_spans=(
            SourceSpan(
                source_id=source.source_id,
                source_blob_id=source.blob_id,
                page_index=0,
                source_object_id="page:875:block:4",
                bounding_box=(
                    96.88088989257812,
                    132.24993896484375,
                    165.281982421875,
                    551.9500122070312,
                ),
            ),
        ),
        extraction_method="pymupdf-text-dict",
        confidence=1.0,
        text=_PRESSURE_LIST,
    )
    document = ExtractedDocument.create(
        source=source,
        pages=(
            ExtractedPage(
                page_index=0,
                width=912.0,
                height=1200.0,
                blocks=(block,),
                coordinate_system=PYMUPDF_COORDINATE_SYSTEM,
            ),
        ),
    )
    return payload, document, block


def test__equation_detector__retains_overlimit_inline_block_as_prose() -> None:
    payload, document, block = _document()
    detector = DeterministicEquationCandidateDetector(
        region_renderer=_UnexpectedRenderer()
    )

    first = detector.detect(document, BytesIO(payload))
    second = detector.detect(document, BytesIO(payload))

    assert first == second
    assert first.processor_version == "2"
    assert first.candidates == ()
    assert first.detection_input.document.pages[0].blocks[0].text == (
        _PRESSURE_LIST
    )
    assert len(first.warnings) == 1
    warning = first.warnings[0]
    assert warning.code == "equation.inline_candidate_limit"
    assert warning.severity is WarningSeverity.WARNING
    assert warning.object_ids == (block.block_id,)
    assert warning.source_spans == block.source_spans
    assert warning.evidence == (
        ("inline_candidate_count", "10"),
        ("max_inline_candidates_per_block", "8"),
    )
