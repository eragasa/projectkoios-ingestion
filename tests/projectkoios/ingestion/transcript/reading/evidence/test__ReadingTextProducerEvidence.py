from dataclasses import replace

import pytest
from projectkoios.ingestion.artifact.managed.media.type import (
    ManagedArtifactMediaType,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.input.document import (
    ReadingDocumentProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.page.evidence import (  # noqa: E501
    ReadingPageTextProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.page.inventory import (  # noqa: E501
    ReadingPageTextProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.status.review import (
    ReadingReviewStatus,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.evidence import (
    ReadingTextStreamEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.inventory import (  # noqa: E501
    ReadingTextStreamEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.kind import (
    ReadingTextStreamKind,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.selection.basis import (  # noqa: E501
    ReadingTextSelectionBasis,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.selection.definition import (  # noqa: E501
    ReadingTextSelection,
)

from .fixture import ReadingEvidenceFoundationFixture


def test__reading_text_streams__retain_native_and_ocr_independently(
    reading_evidence_fixture: ReadingEvidenceFoundationFixture,
) -> None:
    page = reading_evidence_fixture.page()
    native = next(iter(reading_evidence_fixture.native_streams(page=page)))
    ocr = ReadingTextStreamEvidence(
        kind=ReadingTextStreamKind.OCR,
        page_location=page,
        text="OCR page text.",
        upstream_id=reading_evidence_fixture.identity(
            ReadingEvidenceIdentityKind.OCR_RESULT, "ocr"
        ),
        producer_id=reading_evidence_fixture.identity(
            ReadingEvidenceIdentityKind.PRODUCER, "ocr"
        ),
        composition_id=reading_evidence_fixture.identity(
            ReadingEvidenceIdentityKind.COMPOSITION, "ocr"
        ),
        automated=True,
        accepted=False,
        review_status=ReadingReviewStatus.UNREVIEWED,
    )
    streams = ReadingTextStreamEvidenceInventory(native, ocr)

    selection = ReadingTextSelection(
        streams=streams,
        selected_stream_id=ocr.stream_id,
        basis=ReadingTextSelectionBasis.OCR_COMPOSITION_EXACT,
    )

    assert len(streams) == 2
    assert selection.selected_stream_id == ocr.stream_id
    assert selection.producer_id == ocr.producer_id
    assert selection.composition_id == ocr.composition_id
    assert next(iter(streams)).text == "Native page text."


def test__reading_text_stream__allows_exact_empty_native_evidence(
    reading_evidence_fixture: ReadingEvidenceFoundationFixture,
) -> None:
    stream = ReadingTextStreamEvidence(
        kind=ReadingTextStreamKind.NATIVE,
        page_location=reading_evidence_fixture.page(),
        text="",
        upstream_id=reading_evidence_fixture.identity(
            ReadingEvidenceIdentityKind.EXTRACTION_RESULT, "empty"
        ),
        producer_id=reading_evidence_fixture.identity(
            ReadingEvidenceIdentityKind.PRODUCER, "native"
        ),
        composition_id=None,
        automated=True,
        accepted=False,
        review_status=ReadingReviewStatus.UNREVIEWED,
    )

    assert stream.text == ""
    assert stream.utf8_byte_length == 0


def test__reading_text_stream__rejects_conflicting_acceptance_state(
    reading_evidence_fixture: ReadingEvidenceFoundationFixture,
) -> None:
    with pytest.raises(ValueError, match="accepted state conflicts"):
        ReadingTextStreamEvidence(
            kind=ReadingTextStreamKind.NATIVE,
            page_location=reading_evidence_fixture.page(),
            text="text",
            upstream_id=reading_evidence_fixture.identity(
                ReadingEvidenceIdentityKind.EXTRACTION_RESULT, "native"
            ),
            producer_id=reading_evidence_fixture.identity(
                ReadingEvidenceIdentityKind.PRODUCER, "native"
            ),
            composition_id=None,
            automated=True,
            accepted=True,
            review_status=ReadingReviewStatus.UNREVIEWED,
        )


def test__reading_text_selection__rejects_mismatched_basis(
    reading_evidence_fixture: ReadingEvidenceFoundationFixture,
) -> None:
    streams = reading_evidence_fixture.native_streams()
    native = next(iter(streams))

    with pytest.raises(ValueError, match="ocr selection"):
        ReadingTextSelection(
            streams=streams,
            selected_stream_id=native.stream_id,
            basis=ReadingTextSelectionBasis.OCR_COMPOSITION_EXACT,
        )


def test__reading_text_stream__recomputes_content_identity(
    reading_evidence_fixture: ReadingEvidenceFoundationFixture,
) -> None:
    native = next(iter(reading_evidence_fixture.native_streams()))

    changed = replace(native, text="changed")

    assert changed.stream_id != native.stream_id
    assert changed.text_sha256 != native.text_sha256


def test__page_text_producer_inventory__requires_contiguous_pages(
    reading_evidence_fixture: ReadingEvidenceFoundationFixture,
) -> None:
    streams = reading_evidence_fixture.native_streams(
        page=reading_evidence_fixture.page(1)
    )
    record = ReadingPageTextProducerEvidence(
        streams=streams,
        selection=reading_evidence_fixture.native_selection(streams),
        producer_id=reading_evidence_fixture.identity(
            ReadingEvidenceIdentityKind.PRODUCER, "page"
        ),
        producer_version="1",
        review_status=ReadingReviewStatus.UNREVIEWED,
    )

    with pytest.raises(ValueError, match="contiguous"):
        ReadingPageTextProducerEvidenceInventory(record)


def test__document_producer__binds_pdf_source_and_page_expectation(
    reading_evidence_fixture: ReadingEvidenceFoundationFixture,
) -> None:
    record = ReadingDocumentProducerEvidence(
        document_id=reading_evidence_fixture.identity(
            ReadingEvidenceIdentityKind.DOCUMENT, "book"
        ),
        source_id=reading_evidence_fixture.identity(
            ReadingEvidenceIdentityKind.SOURCE, "book"
        ),
        source_artifact=reading_evidence_fixture.artifact(
            media_type=ManagedArtifactMediaType.APPLICATION_PDF
        ),
        title="Example book",
        expected_page_count=1,
        extraction_result_id=reading_evidence_fixture.identity(
            ReadingEvidenceIdentityKind.EXTRACTION_RESULT, "book"
        ),
        producer_id=reading_evidence_fixture.identity(
            ReadingEvidenceIdentityKind.PRODUCER, "document"
        ),
        producer_version="1",
    )

    assert record.expected_page_count == 1
    assert record.source_sha256 == reading_evidence_fixture.digest
    assert (
        record.source_artifact.media_type
        is ManagedArtifactMediaType.APPLICATION_PDF
    )
