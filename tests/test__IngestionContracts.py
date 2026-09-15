from dataclasses import FrozenInstanceError

import pytest
from projectkoios.ingestion import (
    CONTRACT_VERSION,
    ExtractedBlock,
    ExtractedDocument,
    ExtractedPage,
    ExtractionResult,
    IngestionManifest,
    IngestionStatus,
    IngestionWarning,
    SourceDocument,
    SourceSpan,
    TableOfContentsEntry,
    WarningSeverity,
    contract_dict,
    serialize_contract,
)


def make_source(locator: str = "memory://textbook.pdf") -> SourceDocument:
    return SourceDocument.from_bytes(
        b"a deterministic PDF fixture",
        source_id="textbook:fixture",
        media_type="application/pdf",
        locator=locator,
    )


def make_span(source: SourceDocument) -> SourceSpan:
    return SourceSpan(
        source_id=source.source_id,
        source_blob_id=source.blob_id,
        page_index=2,
        printed_page_label="1",
        source_object_id="block-7",
        bounding_box=(10.0, 20.0, 300.0, 80.0),
    )


def make_block(source: SourceDocument) -> ExtractedBlock:
    return ExtractedBlock.create(
        kind="text",
        source_spans=(make_span(source),),
        extraction_method="fixture",
        confidence=1.0,
        text="Charge carriers move under an applied field.",
    )


def make_document(source: SourceDocument) -> ExtractedDocument:
    page = ExtractedPage(
        page_index=2,
        printed_page_label="1",
        width=612.0,
        height=792.0,
        blocks=(make_block(source),),
    )
    return ExtractedDocument.create(source=source, pages=(page,))


def test__source_document__locator_does_not_change_identity() -> None:
    first = make_source("file:///library/textbook.pdf")
    second = make_source("https://example.test/textbook.pdf")

    assert first.source_id == second.source_id
    assert first.blob_id == second.blob_id
    assert first.locator != second.locator


def test__source_document__separates_logical_and_blob_identity() -> None:
    first = SourceDocument.from_bytes(
        b"first PDF revision",
        source_id="textbook:fixture",
        media_type="application/pdf",
        locator="memory://first.pdf",
    )
    second = SourceDocument.from_bytes(
        b"second PDF revision",
        source_id="textbook:fixture",
        media_type="application/pdf",
        locator="memory://second.pdf",
    )

    assert first.source_id == second.source_id
    assert first.blob_id != second.blob_id
    assert first.content_hash != second.content_hash


def test__source_revision__keeps_document_id_and_invalidates_cache() -> None:
    first_source = SourceDocument.from_bytes(
        b"first PDF revision",
        source_id="textbook:fixture",
        media_type="application/pdf",
        locator="memory://first.pdf",
    )
    second_source = SourceDocument.from_bytes(
        b"second PDF revision",
        source_id="textbook:fixture",
        media_type="application/pdf",
        locator="memory://second.pdf",
    )
    first_document = ExtractedDocument.create(
        source=first_source,
        pages=(),
    )
    second_document = ExtractedDocument.create(
        source=second_source,
        pages=(),
    )
    manifest_values = {
        "extractor_name": "fixture",
        "extractor_version": "1.0",
        "configuration_digest": "sha256:configuration",
        "warning_ids": (),
        "status": IngestionStatus.COMPLETED,
        "started_at": "2026-01-01T00:00:00Z",
    }
    first_manifest = IngestionManifest.create(
        source=first_source,
        object_ids=(first_document.document_id,),
        **manifest_values,
    )
    second_manifest = IngestionManifest.create(
        source=second_source,
        object_ids=(second_document.document_id,),
        **manifest_values,
    )

    assert first_document.document_id == second_document.document_id
    assert first_manifest.cache_key != second_manifest.cache_key


def test__source_document__is_immutable() -> None:
    source = make_source()

    with pytest.raises(FrozenInstanceError):
        source.locator = "file:///changed.pdf"  # type: ignore[misc]


def test__extracted_block__has_stable_source_derived_identity() -> None:
    source = make_source()
    first = make_block(source)
    second = ExtractedBlock.create(
        kind="text",
        source_spans=(make_span(source),),
        extraction_method="improved-extractor",
        confidence=0.9,
        text="Cleaned text can change without changing source identity.",
    )

    assert first.block_id == second.block_id


def test__source_span__rejects_invalid_coordinates() -> None:
    source = make_source()

    with pytest.raises(ValueError, match="ordered coordinates"):
        SourceSpan(
            source_id=source.source_id,
            source_blob_id=source.blob_id,
            page_index=0,
            bounding_box=(20.0, 10.0, 5.0, 40.0),
        )


@pytest.mark.parametrize("rotation", [-90, 45, 360, True, 90.0])
def test__extracted_page__rejects_invalid_rotation(rotation: object) -> None:
    source = make_source()

    with pytest.raises(ValueError, match="rotation_degrees"):
        ExtractedPage(
            page_index=2,
            width=612.0,
            height=792.0,
            blocks=(make_block(source),),
            rotation_degrees=rotation,  # type: ignore[arg-type]
        )


def test__document__rejects_blocks_from_another_source() -> None:
    source = make_source()
    other = SourceDocument.from_bytes(
        b"another source",
        source_id="textbook:other",
        media_type="application/pdf",
        locator="memory://other.pdf",
    )
    page = ExtractedPage(
        page_index=2,
        width=612.0,
        height=792.0,
        blocks=(make_block(other),),
    )

    with pytest.raises(ValueError, match="document source"):
        ExtractedDocument.create(source=source, pages=(page,))


def test__manifest__cache_identity_excludes_run_timestamps() -> None:
    source = make_source()
    document = make_document(source)
    values = {
        "source": source,
        "extractor_name": "fixture",
        "extractor_version": "1.0",
        "configuration_digest": "sha256:configuration",
        "object_ids": (document.document_id,),
        "warning_ids": (),
        "status": IngestionStatus.COMPLETED,
    }

    first = IngestionManifest.create(
        **values,
        started_at="2026-01-01T00:00:00Z",
        completed_at="2026-01-01T00:01:00Z",
    )
    second = IngestionManifest.create(
        **values,
        started_at="2027-01-01T00:00:00Z",
        completed_at="2027-01-01T00:01:00Z",
    )

    assert first.cache_key == second.cache_key
    assert first.manifest_id == second.manifest_id


def test__serialization__is_deterministic_and_json_compatible() -> None:
    source = make_source()
    entry = TableOfContentsEntry.create(
        source=source,
        level=1,
        title="Introduction",
        destination=make_span(source),
        source_object_id="pdf-outline-xref:7",
    )
    base_document = make_document(source)
    document = ExtractedDocument.create(
        source=source,
        pages=base_document.pages,
        table_of_contents=(entry,),
    )

    first = serialize_contract(document)
    second = serialize_contract(document)
    values = contract_dict(document)

    assert first == second
    assert values["contract_version"] == "2.2"
    assert values["source"]["content_hash"] == source.content_hash
    assert values["pages"][0]["blocks"][0]["kind"] == "text"
    assert values["table_of_contents"][0]["title"] == "Introduction"


def test__contract_2_2__keeps_additive_fields() -> None:
    document = make_document(make_source())

    assert CONTRACT_VERSION == "2.2"
    assert document.contract_version == CONTRACT_VERSION
    assert document.table_of_contents == ()
    assert document.pages[0].rotation_degrees == 0


def test__contract_2_2__preserves_positional_construction() -> None:
    source = make_source()
    factory_document = make_document(source)
    page = ExtractedPage(
        2,
        612.0,
        792.0,
        (make_block(source),),
        "1",
        1.0,
        (),
        "legacy-coordinate-system",
    )

    document = ExtractedDocument(
        factory_document.document_id,
        source,
        factory_document.pages,
        (),
        ("warning:legacy",),
        "2.0",
    )

    assert page.rotation_degrees == 0
    assert document.warning_ids == ("warning:legacy",)
    assert document.contract_version == "2.0"
    assert document.table_of_contents == ()


def test__extraction_result__requires_manifest_warning_consistency() -> None:
    source = make_source()
    document = make_document(source)
    warning = IngestionWarning.create(
        code="pdf.low_text_density",
        severity=WarningSeverity.WARNING,
        message="The page may require OCR.",
        source_spans=(make_span(source),),
    )
    manifest = IngestionManifest.create(
        source=source,
        extractor_name="fixture",
        extractor_version="1.0",
        configuration_digest="sha256:configuration",
        object_ids=(document.document_id,),
        warning_ids=(),
        status=IngestionStatus.COMPLETED,
        started_at="2026-01-01T00:00:00Z",
    )

    with pytest.raises(ValueError, match="warning IDs"):
        ExtractionResult(
            document=document,
            manifest=manifest,
            warnings=(warning,),
        )
