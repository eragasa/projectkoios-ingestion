from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from io import BytesIO
from pathlib import Path

import pytest
from projectkoios.ingestion import (
    DeterministicLayoutProcessor,
    ExtractedBlock,
    ExtractedPage,
    LayoutAnalysisLimitError,
    LayoutBlockReference,
    LayoutConfiguration,
    LayoutGroupHypothesis,
    LayoutGroupKind,
    LayoutPageKind,
    PageLayoutResult,
    SourceDocument,
    SourceSpan,
)
from projectkoios.ingestion.pdf import (
    PYMUPDF_COORDINATE_SYSTEM,
    PyMuPdfExtractor,
)

FIXTURES = Path(__file__).parent / "fixtures" / "pdf"


def _fixture(fixture_id: str):
    payload = (FIXTURES / f"{fixture_id}.pdf").read_bytes()
    source = SourceDocument.from_bytes(
        payload,
        source_id=f"fixture:{fixture_id}",
        media_type="application/pdf",
        locator=f"fixture://{fixture_id}.pdf",
    )
    extraction = PyMuPdfExtractor(low_text_character_threshold=0).extract(
        source, BytesIO(payload)
    )
    return source, extraction.document


def _texts_in_order(result, page: ExtractedPage) -> list[str | None]:
    blocks = {block.block_id: block for block in page.blocks}
    return [blocks[block_id].text for block_id in result.proposed_order]


def _page(
    blocks: tuple[ExtractedBlock, ...],
    *,
    width: float = 100.0,
    height: float = 100.0,
    rotation_degrees: int = 0,
    coordinate_system: str = PYMUPDF_COORDINATE_SYSTEM,
) -> ExtractedPage:
    return ExtractedPage(
        page_index=0,
        width=width,
        height=height,
        blocks=blocks,
        coordinate_system=coordinate_system,
        rotation_degrees=rotation_degrees,
    )


def _block(
    source: SourceDocument,
    ordinal: int,
    box: tuple[float, float, float, float] | None,
) -> ExtractedBlock:
    return ExtractedBlock.create(
        kind="text",
        source_spans=(
            SourceSpan(
                source_id=source.source_id,
                source_blob_id=source.blob_id,
                page_index=0,
                source_object_id=f"page:0:block:{ordinal}",
                bounding_box=box,
            ),
        ),
        extraction_method="fixture",
        confidence=1.0,
        text=f"block {ordinal}",
    )


def test__layout__one_column_is_deterministic_and_preserves_raw_blocks() -> (
    None
):
    source, document = _fixture("born-digital-text")
    page = document.pages[0]
    raw_before = page.blocks
    processor = DeterministicLayoutProcessor()

    first = processor.analyze_page(source, page)
    second = processor.analyze(document)[0]

    assert first == second
    assert first.result_id == second.result_id
    assert first.page_kind is LayoutPageKind.ONE_COLUMN
    assert [group.kind for group in first.groups] == [
        LayoutGroupKind.ONE_COLUMN
    ]
    assert first.proposed_order == (page.blocks[0].block_id,)
    assert page.blocks is raw_before
    assert first.raw_block_ids == tuple(block.block_id for block in page.blocks)
    assert first.processor_name == "deterministic-page-layout"
    assert first.processor_version == "2"


def test__layout__two_columns_override_only_the_derived_proposal() -> None:
    source, document = _fixture("two-column-layout")
    page = document.pages[0]
    native_text = [block.text for block in page.blocks]

    result = DeterministicLayoutProcessor().analyze_page(source, page)

    first_native = native_text[0]
    first_proposed = _texts_in_order(result, page)[0]
    assert first_native is not None and first_native.startswith("RIGHT")
    assert first_proposed is not None and first_proposed.startswith("LEFT")
    assert [group.kind for group in result.groups] == [
        LayoutGroupKind.COLUMN,
        LayoutGroupKind.COLUMN,
    ]
    assert result.page_kind is LayoutPageKind.MULTI_COLUMN
    assert result.warnings == ()
    assert [block.text for block in page.blocks] == native_text


def test__layout__spanning_heading_precedes_columns() -> None:
    source, document = _fixture("spanning-heading")
    page = document.pages[0]
    assert page.blocks[-1].text is not None
    assert page.blocks[-1].text.startswith("SPANNING")

    result = DeterministicLayoutProcessor().analyze_page(source, page)
    proposed = _texts_in_order(result, page)

    assert proposed[0] is not None and proposed[0].startswith("SPANNING")
    assert proposed[1] is not None and proposed[1].startswith("LEFT")
    assert proposed[2] is not None and proposed[2].startswith("RIGHT")
    assert [group.kind for group in result.groups] == [
        LayoutGroupKind.SPANNING_HEADING,
        LayoutGroupKind.COLUMN,
        LayoutGroupKind.COLUMN,
    ]


def test__layout__footnote_candidate_follows_main_flow_uncertainly() -> None:
    source, document = _fixture("footnote-layout")
    page = document.pages[0]
    assert page.blocks[0].text is not None
    assert page.blocks[0].text.startswith("1 Footnote")

    result = DeterministicLayoutProcessor().analyze_page(source, page)
    proposed = _texts_in_order(result, page)

    assert proposed[0] is not None and proposed[0].startswith("Main flow")
    assert proposed[-1] is not None and proposed[-1].startswith("1 Footnote")
    assert result.page_kind is LayoutPageKind.AMBIGUOUS
    assert result.groups[-1].kind is LayoutGroupKind.FOOTNOTE_CANDIDATE
    assert result.groups[-1].confidence < 0.5
    assert result.warnings[-1].code == (
        "layout.separated_bottom_text_ambiguous"
    )
    assert dict(result.groups[-1].evidence)["position"] == (
        "separated_near_page_bottom"
    )


def test__layout__sidebar_remains_an_explicit_uncertain_hypothesis() -> None:
    source, document = _fixture("sidebar-layout")

    result = DeterministicLayoutProcessor().analyze(document)[0]

    assert result.page_kind is LayoutPageKind.AMBIGUOUS
    assert LayoutGroupKind.SIDEBAR in {group.kind for group in result.groups}
    assert result.confidence < 0.5
    assert [warning.code for warning in result.warnings] == [
        "layout.sidebar_order_ambiguous"
    ]
    sidebar = next(
        group
        for group in result.groups
        if group.kind is LayoutGroupKind.SIDEBAR
    )
    assert sidebar.warning_ids == (result.warnings[0].warning_id,)
    assert dict(sidebar.evidence)["ordering"] == "uncertain"


def test__layout__weak_separation_is_ambiguous_not_a_guessed_column_order() -> (
    None
):
    source, document = _fixture("ambiguous-overlap")

    result = DeterministicLayoutProcessor().analyze(document)[0]

    assert result.page_kind is LayoutPageKind.AMBIGUOUS
    assert result.groups[0].kind is LayoutGroupKind.UNCERTAIN
    assert result.confidence == 0.25
    assert [warning.code for warning in result.warnings] == [
        "layout.weak_column_separation_ambiguous"
    ]


def test__layout__overlapping_blocks_are_explicitly_ambiguous() -> None:
    source = SourceDocument.from_bytes(
        b"fixture",
        source_id="fixture:overlap",
        media_type="application/pdf",
        locator="memory://fixture.pdf",
    )
    blocks = (
        _block(source, 0, (10.0, 10.0, 60.0, 40.0)),
        _block(source, 1, (40.0, 20.0, 90.0, 50.0)),
    )
    page = ExtractedPage(
        page_index=0,
        width=100.0,
        height=100.0,
        blocks=blocks,
        coordinate_system=PYMUPDF_COORDINATE_SYSTEM,
    )

    result = DeterministicLayoutProcessor().analyze_page(source, page)

    assert result.page_kind is LayoutPageKind.AMBIGUOUS
    assert result.confidence == 0.25
    assert result.warnings[0].code == "layout.overlapping_blocks_ambiguous"


def test__layout__non_text_blocks_are_recorded_but_not_claimed_as_text() -> (
    None
):
    source, document = _fixture("image-only-page")
    page = document.pages[0]

    result = DeterministicLayoutProcessor().analyze_page(source, page)

    assert result.page_kind is LayoutPageKind.EMPTY
    assert result.proposed_order == ()
    assert result.input_text_blocks == ()
    assert result.non_text_block_ids == (page.blocks[0].block_id,)
    assert result.raw_block_ids == (page.blocks[0].block_id,)
    assert page.blocks[0].kind == "image"


def test__layout__missing_geometry_is_explicitly_excluded() -> None:
    source = SourceDocument.from_bytes(
        b"fixture",
        source_id="fixture:missing",
        media_type="application/pdf",
        locator="memory://fixture.pdf",
    )
    block = _block(source, 0, None)
    page = ExtractedPage(
        page_index=0,
        width=100.0,
        height=100.0,
        blocks=(block,),
        coordinate_system=PYMUPDF_COORDINATE_SYSTEM,
    )

    result = DeterministicLayoutProcessor().analyze_page(source, page)

    assert result.page_kind is LayoutPageKind.AMBIGUOUS
    assert result.confidence == 0.0
    assert result.proposed_order == ()
    assert [(item.block_id, item.reason) for item in result.exclusions] == [
        (block.block_id, "missing_bounding_box")
    ]
    assert result.warnings[0].code == "layout.text_geometry_excluded"


def test__layout__bounds_work_before_pairwise_analysis() -> None:
    source = SourceDocument.from_bytes(
        b"fixture",
        source_id="fixture:limit",
        media_type="application/pdf",
        locator="memory://fixture.pdf",
    )
    blocks = tuple(
        _block(source, ordinal, (0.0, float(ordinal), 10.0, ordinal + 0.5))
        for ordinal in range(3)
    )
    page = ExtractedPage(
        page_index=0,
        width=100.0,
        height=100.0,
        blocks=blocks,
        coordinate_system=PYMUPDF_COORDINATE_SYSTEM,
    )
    processor = DeterministicLayoutProcessor(
        LayoutConfiguration(max_text_blocks_per_page=2)
    )

    with pytest.raises(LayoutAnalysisLimitError, match="max_text_blocks"):
        processor.analyze_page(source, page)


def test__layout__bounds_source_span_count() -> None:
    source = SourceDocument.from_bytes(
        b"fixture",
        source_id="fixture:span-limit",
        media_type="application/pdf",
        locator="memory://fixture.pdf",
    )
    spans = tuple(
        SourceSpan(
            source_id=source.source_id,
            source_blob_id=source.blob_id,
            page_index=0,
            source_object_id=f"line:{index}",
            bounding_box=(0.0, float(index), 10.0, index + 0.5),
        )
        for index in range(3)
    )
    block = ExtractedBlock.create(
        kind="text",
        source_spans=spans,
        extraction_method="fixture",
        confidence=1.0,
        text="three spans",
    )
    page = ExtractedPage(
        page_index=0,
        width=100.0,
        height=100.0,
        blocks=(block,),
        coordinate_system=PYMUPDF_COORDINATE_SYSTEM,
    )
    processor = DeterministicLayoutProcessor(
        LayoutConfiguration(max_source_spans_per_page=2)
    )

    with pytest.raises(LayoutAnalysisLimitError, match="source span count"):
        processor.analyze_page(source, page)


def test__layout__rejects_non_finite_geometry() -> None:
    source = SourceDocument.from_bytes(
        b"fixture",
        source_id="fixture:nan",
        media_type="application/pdf",
        locator="memory://fixture.pdf",
    )
    page = ExtractedPage(
        page_index=0,
        width=100.0,
        height=100.0,
        blocks=(_block(source, 0, (0.0, 0.0, float("nan"), 10.0)),),
        coordinate_system=PYMUPDF_COORDINATE_SYSTEM,
    )

    with pytest.raises(ValueError, match="finite number"):
        DeterministicLayoutProcessor().analyze_page(source, page)


def test__layout__direct_construction_validates_identity_and_cross_links() -> (
    None
):
    source, document = _fixture("two-column-layout")
    result = DeterministicLayoutProcessor().analyze(document)[0]

    with pytest.raises(ValueError, match="result ID"):
        replace(result, result_id="page-layout-result:sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="cover all text blocks"):
        replace(result, proposed_order=result.proposed_order[:-1])
    with pytest.raises(ValueError, match="one group"):
        replace(result, groups=result.groups[:-1])
    with pytest.raises(ValueError, match="exactly match raw text blocks"):
        bad_reference = replace(
            result.input_text_blocks[0],
            source_spans=(
                replace(
                    result.input_text_blocks[0].source_spans[0], page_index=1
                ),
            ),
        )
        replace(
            result,
            input_text_blocks=(bad_reference, *result.input_text_blocks[1:]),
        )
    with pytest.raises(ValueError, match="warning"):
        _, sidebar_document = _fixture("sidebar-layout")
        sidebar_result = DeterministicLayoutProcessor().analyze(
            sidebar_document
        )[0]
        replace(sidebar_result, warnings=())
    with pytest.raises(FrozenInstanceError):
        result.confidence = 1.0  # type: ignore[misc]


def test__layout__configuration_and_processor_identity_enter_result_id() -> (
    None
):
    source, document = _fixture("born-digital-text")
    first = DeterministicLayoutProcessor().analyze(document)[0]
    changed = DeterministicLayoutProcessor(
        LayoutConfiguration(minimum_column_gap_ratio=0.05)
    ).analyze(document)[0]

    assert first.configuration_digest != changed.configuration_digest
    assert first.result_id != changed.result_id


def test__layout_reference__canonicalizes_negative_zero() -> None:
    source = SourceDocument.from_bytes(
        b"fixture",
        source_id="fixture:zero",
        media_type="application/pdf",
        locator="memory://fixture.pdf",
    )
    block = _block(source, 0, (-0.0, -0.0, 10.0, 10.0))

    reference = LayoutBlockReference.from_block(block)

    assert reference.source_spans[0].bounding_box == (0.0, 0.0, 10.0, 10.0)


def test__layout__group_claims_participate_in_stable_identity() -> None:
    source, document = _fixture("two-column-layout")
    result = DeterministicLayoutProcessor().analyze(document)[0]
    with pytest.raises(ValueError, match="group ID"):
        replace(result.groups[0], confidence=0.1)

    footnote_source, footnote_document = _fixture("footnote-layout")
    footnote_result = DeterministicLayoutProcessor().analyze(
        footnote_document
    )[0]
    with pytest.raises(ValueError, match="group ID"):
        replace(footnote_result.groups[-1], warning_ids=())
    assert footnote_source.source_id == footnote_result.source_id


def test__layout__fresh_footnote_candidate_requires_warning_link() -> None:
    source, document = _fixture("footnote-layout")
    page = document.pages[0]
    result = DeterministicLayoutProcessor().analyze_page(source, page)
    valid_candidate = result.groups[-1]
    warning_free_candidate = LayoutGroupHypothesis.create(
        source_id=source.source_id,
        source_blob_id=source.blob_id,
        page_index=page.page_index,
        kind=LayoutGroupKind.FOOTNOTE_CANDIDATE,
        block_ids=valid_candidate.block_ids,
        bounding_box=valid_candidate.bounding_box,
        evidence=valid_candidate.evidence,
        confidence=valid_candidate.confidence,
        warning_ids=(),
    )

    with pytest.raises(ValueError, match="candidates must link"):
        PageLayoutResult.create(
            source=source,
            page=page,
            input_text_blocks=result.input_text_blocks,
            non_text_block_ids=result.non_text_block_ids,
            proposed_order=result.proposed_order,
            exclusions=result.exclusions,
            groups=(*result.groups[:-1], warning_free_candidate),
            page_kind=result.page_kind,
            evidence=result.evidence,
            confidence=result.confidence,
            warnings=result.warnings,
            processor_name=result.processor_name,
            processor_version=result.processor_version,
            configuration_digest=result.configuration_digest,
        )

    assert valid_candidate.warning_ids


def test__layout_factory__rejects_swapped_kinds_and_fabricated_spans() -> None:
    source, document = _fixture("figures")
    page = document.pages[0]
    result = DeterministicLayoutProcessor().analyze_page(source, page)
    image_reference = LayoutBlockReference.from_block(page.blocks[0])
    text_reference = result.input_text_blocks[0]
    values = {
        "source": source,
        "page": page,
        "proposed_order": result.proposed_order,
        "exclusions": result.exclusions,
        "groups": result.groups,
        "page_kind": result.page_kind,
        "evidence": result.evidence,
        "confidence": result.confidence,
        "warnings": result.warnings,
        "processor_name": result.processor_name,
        "processor_version": result.processor_version,
        "configuration_digest": result.configuration_digest,
    }

    with pytest.raises(ValueError, match="raw text blocks"):
        PageLayoutResult.create(
            input_text_blocks=(image_reference,),
            non_text_block_ids=(text_reference.block_id,),
            **values,
        )

    fabricated = replace(
        text_reference,
        source_spans=(
            replace(
                text_reference.source_spans[0],
                source_object_id="fabricated-same-page-span",
            ),
        ),
    )
    with pytest.raises(ValueError, match="raw text blocks"):
        PageLayoutResult.create(
            input_text_blocks=(fabricated,),
            non_text_block_ids=result.non_text_block_ids,
            **values,
        )


def test__layout__combined_exclusion_warning_is_not_linked_to_group() -> None:
    source = SourceDocument.from_bytes(
        b"fixture",
        source_id="fixture:combined-warning",
        media_type="application/pdf",
        locator="memory://fixture.pdf",
    )
    blocks = (
        _block(source, 0, None),
        _block(source, 1, (10.0, 10.0, 60.0, 40.0)),
        _block(source, 2, (40.0, 20.0, 90.0, 50.0)),
    )

    result = DeterministicLayoutProcessor().analyze_page(
        source, _page(blocks)
    )

    warnings = {warning.code: warning for warning in result.warnings}
    assert set(warnings) == {
        "layout.text_geometry_excluded",
        "layout.overlapping_blocks_ambiguous",
    }
    assert warnings["layout.text_geometry_excluded"].warning_id not in (
        result.groups[0].warning_ids
    )
    assert warnings["layout.overlapping_blocks_ambiguous"].warning_id in (
        result.groups[0].warning_ids
    )


def test__layout__rejects_unsupported_coordinates_and_marks_rotation() -> None:
    source = SourceDocument.from_bytes(
        b"fixture",
        source_id="fixture:coordinates",
        media_type="application/pdf",
        locator="memory://fixture.pdf",
    )
    block = _block(source, 0, (10.0, 10.0, 90.0, 30.0))

    with pytest.raises(ValueError, match="coordinate system"):
        DeterministicLayoutProcessor().analyze_page(
            source, _page((block,), coordinate_system="unspecified")
        )

    rotated = DeterministicLayoutProcessor().analyze_page(
        source, _page((block,), rotation_degrees=90)
    )
    assert rotated.rotation_degrees == 90
    assert rotated.page_kind is LayoutPageKind.AMBIGUOUS
    assert rotated.warnings[-1].code == "layout.rotated_page_ambiguous"
    assert rotated.confidence == 0.25


def test__layout__extracts_all_rotations_and_marks_nonzero_ambiguous() -> None:
    pymupdf = pytest.importorskip("pymupdf")
    document = pymupdf.open()
    for rotation in (0, 90, 180, 270):
        page = document.new_page(width=200, height=300)
        page.set_cropbox(pymupdf.Rect(10, 20, 190, 280))
        page.insert_text((30, 60), f"rotation {rotation} evidence")
        page.set_rotation(rotation)
    payload = document.tobytes()
    document.close()
    source = SourceDocument.from_bytes(
        payload,
        source_id="fixture:rotations",
        media_type="application/pdf",
        locator="memory://rotations.pdf",
    )
    extracted = PyMuPdfExtractor(low_text_character_threshold=0).extract(
        source, BytesIO(payload)
    ).document

    assert [page.rotation_degrees for page in extracted.pages] == [
        0,
        90,
        180,
        270,
    ]
    results = DeterministicLayoutProcessor().analyze(extracted)
    assert results[0].page_kind is LayoutPageKind.ONE_COLUMN
    for rotation, result in zip((90, 180, 270), results[1:], strict=True):
        assert result.rotation_degrees == rotation
        assert result.page_kind is LayoutPageKind.AMBIGUOUS
        assert result.warnings[-1].code == "layout.rotated_page_ambiguous"


def test__layout__staggered_and_sparse_side_groups_remain_ambiguous() -> None:
    source = SourceDocument.from_bytes(
        b"fixture",
        source_id="fixture:staggered",
        media_type="application/pdf",
        locator="memory://fixture.pdf",
    )
    staggered = (
        _block(source, 0, (10.0, 10.0, 30.0, 20.0)),
        _block(source, 1, (10.0, 90.0, 30.0, 100.0)),
        _block(source, 2, (60.0, 40.0, 80.0, 50.0)),
    )
    sparse = (
        _block(source, 3, (10.0, 10.0, 30.0, 15.0)),
        _block(source, 4, (60.0, 10.0, 80.0, 15.0)),
    )

    for blocks in (staggered, sparse):
        result = DeterministicLayoutProcessor().analyze_page(
            source, _page(blocks)
        )
        assert result.page_kind is LayoutPageKind.AMBIGUOUS
        assert result.confidence == 0.25
        assert result.warnings[-1].code == (
            "layout.discontinuous_side_groups_ambiguous"
        )


def test__layout__multiple_sparse_blocks_per_side_remain_ambiguous() -> None:
    source = SourceDocument.from_bytes(
        b"fixture",
        source_id="fixture:multi-sparse",
        media_type="application/pdf",
        locator="memory://fixture.pdf",
    )
    blocks = (
        _block(source, 0, (0.0, 10.0, 20.0, 12.0)),
        _block(source, 1, (0.0, 13.0, 20.0, 15.0)),
        _block(source, 2, (60.0, 10.0, 80.0, 12.0)),
        _block(source, 3, (60.0, 13.0, 80.0, 15.0)),
    )

    result = DeterministicLayoutProcessor().analyze_page(
        source, _page(blocks)
    )

    assert result.page_kind is LayoutPageKind.AMBIGUOUS
    assert result.confidence == 0.25
    assert result.warnings[-1].code == (
        "layout.discontinuous_side_groups_ambiguous"
    )


def test__layout__qualifying_nested_split_on_either_side_is_ambiguous() -> None:
    source = SourceDocument.from_bytes(
        b"fixture",
        source_id="fixture:nested-splits",
        media_type="application/pdf",
        locator="memory://fixture.pdf",
    )
    blocks = (
        _block(source, 0, (0.0, 10.0, 20.0, 90.0)),
        _block(source, 1, (22.0, 10.0, 42.0, 90.0)),
        _block(source, 2, (61.0, 10.0, 71.0, 90.0)),
        _block(source, 3, (82.0, 10.0, 92.0, 90.0)),
    )

    result = DeterministicLayoutProcessor().analyze_page(
        source, _page(blocks)
    )

    assert result.page_kind is LayoutPageKind.AMBIGUOUS
    assert result.warnings[-1].code == (
        "layout.multiple_column_groups_ambiguous"
    )


def test__layout__touching_columns_and_center_bridge_are_ambiguous() -> None:
    source = SourceDocument.from_bytes(
        b"fixture",
        source_id="fixture:touching",
        media_type="application/pdf",
        locator="memory://fixture.pdf",
    )
    touching = (
        _block(source, 0, (10.0, 20.0, 50.0, 80.0)),
        _block(source, 1, (50.0, 20.0, 90.0, 80.0)),
    )
    touching_result = DeterministicLayoutProcessor().analyze_page(
        source, _page(touching)
    )
    assert touching_result.page_kind is LayoutPageKind.AMBIGUOUS
    assert touching_result.warnings[-1].code == (
        "layout.weak_column_separation_ambiguous"
    )

    bridge = _block(source, 2, (30.0, 0.0, 70.0, 10.0))
    bridged_result = DeterministicLayoutProcessor().analyze_page(
        source,
        _page(
            (
                bridge,
                _block(source, 3, (0.0, 20.0, 40.0, 80.0)),
                _block(source, 4, (60.0, 20.0, 100.0, 80.0)),
            )
        ),
    )
    assert bridged_result.page_kind is LayoutPageKind.AMBIGUOUS
    assert bridged_result.warnings[-1].code == (
        "layout.bridging_block_ambiguous"
    )


def test__layout__wide_left_heading_does_not_become_spanning() -> None:
    source = SourceDocument.from_bytes(
        b"fixture",
        source_id="fixture:false-spanning",
        media_type="application/pdf",
        locator="memory://fixture.pdf",
    )
    blocks = (
        _block(source, 0, (0.0, 0.0, 50.0, 10.0)),
        _block(source, 1, (0.0, 20.0, 20.0, 80.0)),
        _block(source, 2, (70.0, 20.0, 90.0, 80.0)),
    )

    result = DeterministicLayoutProcessor().analyze_page(
        source, _page(blocks)
    )

    assert result.page_kind is LayoutPageKind.AMBIGUOUS
    assert LayoutGroupKind.SPANNING_HEADING not in {
        group.kind for group in result.groups
    }
    assert result.warnings[-1].code == (
        "layout.spanning_position_ambiguous"
    )


def test__layout__separated_footer_is_only_a_footnote_candidate() -> None:
    source = SourceDocument.from_bytes(
        b"fixture",
        source_id="fixture:footer",
        media_type="application/pdf",
        locator="memory://fixture.pdf",
    )
    blocks = (
        _block(source, 0, (10.0, 10.0, 90.0, 50.0)),
        _block(source, 1, (0.0, 85.0, 100.0, 95.0)),
    )

    result = DeterministicLayoutProcessor().analyze_page(
        source, _page(blocks)
    )

    assert result.page_kind is LayoutPageKind.AMBIGUOUS
    candidate = result.groups[-1]
    assert candidate.kind is LayoutGroupKind.FOOTNOTE_CANDIDATE
    assert dict(candidate.evidence)["semantic_role"] == "unverified"
    assert candidate.warning_ids
    assert result.warnings[-1].code == (
        "layout.separated_bottom_text_ambiguous"
    )


def test__layout__bounds_all_raw_evidence_and_identity_strings() -> None:
    source = SourceDocument.from_bytes(
        b"fixture",
        source_id="fixture:hostile",
        media_type="application/pdf",
        locator="memory://fixture.pdf",
    )
    blocks = (
        _block(source, 0, (0.0, 0.0, 10.0, 10.0)),
        _block(source, 1, (20.0, 0.0, 30.0, 10.0)),
    )
    foreign_second = replace(
        blocks[1],
        source_spans=(
            replace(blocks[1].source_spans[0], source_id="foreign"),
        ),
    )
    with pytest.raises(LayoutAnalysisLimitError, match="raw block count"):
        DeterministicLayoutProcessor(
            LayoutConfiguration(max_raw_blocks_per_page=1)
        ).analyze_page(source, _page((blocks[0], foreign_second)))

    long_id_block = replace(blocks[0], block_id="x" * 20)
    with pytest.raises(LayoutAnalysisLimitError, match="identity_field"):
        DeterministicLayoutProcessor(
            LayoutConfiguration(max_identity_field_characters=10)
        ).analyze_page(source, _page((long_id_block,)))

    with pytest.raises(LayoutAnalysisLimitError, match="total_identity"):
        DeterministicLayoutProcessor(
            LayoutConfiguration(max_total_identity_characters=100)
        ).analyze_page(source, _page(blocks))

    non_text_many_spans = replace(
        blocks[0],
        kind="image",
        text=None,
        asset_id="asset:fixture",
        source_spans=tuple(
            replace(blocks[0].source_spans[0], source_object_id=f"image:{i}")
            for i in range(3)
        ),
    )
    with pytest.raises(LayoutAnalysisLimitError, match="source span count"):
        DeterministicLayoutProcessor(
            LayoutConfiguration(max_source_spans_per_page=2)
        ).analyze_page(source, _page((non_text_many_spans,)))


def test__layout__text_kind_without_text_payload_is_excluded() -> None:
    source = SourceDocument.from_bytes(
        b"fixture",
        source_id="fixture:missing-text",
        media_type="application/pdf",
        locator="memory://fixture.pdf",
    )
    span = _block(source, 0, (10.0, 10.0, 90.0, 30.0)).source_spans
    malformed = ExtractedBlock.create(
        kind="text",
        source_spans=span,
        extraction_method="fixture",
        confidence=1.0,
        asset_id="asset:fixture",
    )

    result = DeterministicLayoutProcessor().analyze_page(
        source, _page((malformed,))
    )

    assert result.page_kind is LayoutPageKind.AMBIGUOUS
    assert result.confidence == 0.0
    assert result.exclusions[0].reason == "missing_text_payload"
