from __future__ import annotations

import hashlib
from dataclasses import FrozenInstanceError

import pytest
from projectkoios.ingestion import (
    ExtractedBlock,
    ExtractedDocument,
    ExtractedPage,
    ExtractionResult,
    IngestionManifest,
    IngestionStatus,
    PdfExtractionArtifactIncompleteError,
    PdfExtractionArtifactLimitError,
    PdfExtractionArtifactLimits,
    PdfExtractionArtifactMalformedError,
    PdfExtractionArtifactPayload,
    PdfExtractionConfiguration,
    PdfExtractionTranscript,
    PdfExtractionTranscriptPage,
    SourceDocument,
    SourceSpan,
    build_pdf_extraction_artifacts,
    read_pdf_extraction_transcript,
)

_SOURCE_BYTES = b"%PDF-1.7\nsanitized fixture only\n%%EOF\n"


def _bundle(*, status: IngestionStatus = IngestionStatus.COMPLETED):
    source = SourceDocument.from_bytes(
        _SOURCE_BYTES,
        source_id="reference:sanitized-fixture",
        media_type="application/pdf",
        locator="staged/sanitized-fixture.pdf",
    )
    first_span = SourceSpan(
        source_id=source.source_id,
        source_blob_id=source.blob_id,
        page_index=0,
        printed_page_label="i",
        bounding_box=(10.0, 10.0, 100.0, 30.0),
    )
    second_span = SourceSpan(
        source_id=source.source_id,
        source_blob_id=source.blob_id,
        page_index=0,
        printed_page_label="i",
        bounding_box=(10.0, 40.0, 100.0, 60.0),
    )
    first = ExtractedBlock.create(
        kind="text",
        source_spans=(first_span,),
        extraction_method="sanitized-fixture",
        confidence=1.0,
        text="First line  \nGreek beta: β",
    )
    image = ExtractedBlock.create(
        kind="image",
        source_spans=(first_span,),
        extraction_method="sanitized-fixture",
        confidence=1.0,
        asset_id="asset:sanitized-image",
        asset_media_type="image/png",
    )
    second = ExtractedBlock.create(
        kind="text",
        source_spans=(second_span,),
        extraction_method="sanitized-fixture",
        confidence=1.0,
        text="Second\tblock",
    )
    pages = (
        ExtractedPage(
            page_index=0,
            width=612.0,
            height=792.0,
            blocks=(first, image, second),
            printed_page_label="i",
            coordinate_system="fixture-points",
        ),
        ExtractedPage(
            page_index=1,
            width=612.0,
            height=792.0,
            blocks=(),
            coordinate_system="fixture-points",
        ),
    )
    document = ExtractedDocument.create(
        source=source,
        pages=pages,
        metadata=(("title", "Sanitized example"), ("author", "Test Author")),
    )
    configuration = PdfExtractionConfiguration(
        low_text_character_threshold=40,
        maximum_pages=2,
    )
    manifest = IngestionManifest.create(
        source=source,
        extractor_name="sanitized-fixture-extractor",
        extractor_version="1",
        configuration_digest=configuration.configuration_digest,
        object_ids=(
            document.document_id,
            first.block_id,
            image.block_id,
            second.block_id,
        ),
        warning_ids=(),
        status=status,
        started_at="2026-01-01T00:00:00+00:00",
        completed_at="2026-01-01T00:00:01+00:00",
    )
    limits = PdfExtractionArtifactLimits()
    return build_pdf_extraction_artifacts(
        ExtractionResult(document=document, manifest=manifest),
        configuration=configuration,
        artifact_limits=limits,
    )


def _read(bundle):
    return read_pdf_extraction_transcript(
        bundle.artifacts,
        expected_bundle_id=bundle.bundle_id,
        expected_source_sha256=hashlib.sha256(_SOURCE_BYTES).hexdigest(),
        expected_source_byte_size=len(_SOURCE_BYTES),
        configuration=bundle.configuration,
        artifact_limits=bundle.artifact_limits,
    )


def test__replay_returns_exact_ordered_native_page_text_and_identity() -> None:
    bundle = _bundle()

    transcript = _read(bundle)

    assert isinstance(transcript, PdfExtractionTranscript)
    assert transcript.bundle_id == bundle.bundle_id
    assert transcript.source_id == "reference:sanitized-fixture"
    assert transcript.source_blob_id.startswith("blob:sha256:")
    assert transcript.source_sha256 == hashlib.sha256(_SOURCE_BYTES).hexdigest()
    assert transcript.source_byte_size == len(_SOURCE_BYTES)
    assert transcript.media_type == "application/pdf"
    assert transcript.metadata == (
        ("title", "Sanitized example"),
        ("author", "Test Author"),
    )
    assert transcript.manifest_id == bundle.result.manifest.manifest_id
    assert transcript.status is IngestionStatus.COMPLETED
    assert transcript.review_status == "automated_unreviewed"
    assert tuple(page.page_index for page in transcript.pages) == (0, 1)
    assert transcript.pages[0].printed_page_label == "i"
    assert transcript.pages[0].text == (
        "First line  \nGreek beta: β\n\nSecond\tblock"
    )
    assert transcript.pages[1].printed_page_label is None
    assert transcript.pages[1].text == ""
    assert transcript.pages[0].page_id != transcript.pages[1].page_id
    assert _read(bundle) == transcript
    assert isinstance(transcript.pages[0], PdfExtractionTranscriptPage)
    with pytest.raises(FrozenInstanceError):
        transcript.pages[0].text = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    "artifacts",
    [
        lambda bundle: bundle.artifacts[:-1],
        lambda bundle: bundle.artifacts + (bundle.artifacts[-1],),
        lambda bundle: tuple(reversed(bundle.artifacts)),
    ],
)
def test__replay_rejects_incomplete_duplicate_or_disordered_inventory(
    artifacts,
) -> None:
    bundle = _bundle()

    with pytest.raises(PdfExtractionArtifactIncompleteError):
        read_pdf_extraction_transcript(
            artifacts(bundle),
            expected_bundle_id=bundle.bundle_id,
            expected_source_sha256=hashlib.sha256(_SOURCE_BYTES).hexdigest(),
            expected_source_byte_size=len(_SOURCE_BYTES),
            configuration=bundle.configuration,
            artifact_limits=bundle.artifact_limits,
        )


def test__replay_rejects_noncanonical_json_and_changed_page_text() -> None:
    bundle = _bundle()
    raw = bundle.artifacts[0]
    noncanonical_raw = PdfExtractionArtifactPayload.create(
        relative_path=raw.relative_path,
        media_type=raw.media_type,
        content=b" " + raw.content,
    )
    page = bundle.artifacts[1]
    changed_page = PdfExtractionArtifactPayload.create(
        relative_path=page.relative_path,
        media_type=page.media_type,
        content=page.content.replace(b"Second", b"Changed"),
    )

    for artifacts in (
        (noncanonical_raw, *bundle.artifacts[1:]),
        (bundle.artifacts[0], changed_page, bundle.artifacts[2]),
    ):
        with pytest.raises(PdfExtractionArtifactMalformedError):
            read_pdf_extraction_transcript(
                artifacts,
                expected_bundle_id=bundle.bundle_id,
                expected_source_sha256=hashlib.sha256(
                    _SOURCE_BYTES
                ).hexdigest(),
                expected_source_byte_size=len(_SOURCE_BYTES),
                configuration=bundle.configuration,
                artifact_limits=bundle.artifact_limits,
            )


def test__replay_rejects_source_configuration_bundle_and_status_mismatch() -> (
    None
):
    bundle = _bundle()
    cases = (
        {
            "expected_bundle_id": bundle.bundle_id.removesuffix(
                bundle.bundle_id[-1]
            )
            + ("0" if bundle.bundle_id[-1] != "0" else "1"),
        },
        {"expected_source_sha256": "0" * 64},
        {"expected_source_byte_size": len(_SOURCE_BYTES) + 1},
        {
            "configuration": PdfExtractionConfiguration(
                low_text_character_threshold=41,
                maximum_pages=2,
            )
        },
    )
    base = {
        "expected_bundle_id": bundle.bundle_id,
        "expected_source_sha256": hashlib.sha256(_SOURCE_BYTES).hexdigest(),
        "expected_source_byte_size": len(_SOURCE_BYTES),
        "configuration": bundle.configuration,
        "artifact_limits": bundle.artifact_limits,
    }

    for changed in cases:
        with pytest.raises(PdfExtractionArtifactMalformedError):
            read_pdf_extraction_transcript(
                bundle.artifacts,
                **(base | changed),
            )

    partial = _bundle(status=IngestionStatus.PARTIAL)
    with pytest.raises(PdfExtractionArtifactMalformedError, match="completed"):
        _read(partial)


def test__replay_enforces_caller_supplied_bounds_before_semantic_decode() -> (
    None
):
    bundle = _bundle()

    with pytest.raises(PdfExtractionArtifactLimitError, match="max_artifacts"):
        read_pdf_extraction_transcript(
            bundle.artifacts,
            expected_bundle_id=bundle.bundle_id,
            expected_source_sha256=hashlib.sha256(_SOURCE_BYTES).hexdigest(),
            expected_source_byte_size=len(_SOURCE_BYTES),
            configuration=bundle.configuration,
            artifact_limits=PdfExtractionArtifactLimits(max_artifacts=2),
        )
