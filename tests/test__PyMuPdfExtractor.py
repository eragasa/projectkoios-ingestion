from __future__ import annotations

import hashlib
import importlib.metadata
import sys
from dataclasses import FrozenInstanceError
from io import BytesIO
from pathlib import Path

import pytest
from projectkoios.ingestion import (
    CONTRACT_VERSION,
    contract_dict,
    serialize_contract,
)
from projectkoios.ingestion.cli import (
    ArtifactPublicationError,
    _publish_artifacts,
    main,
)
from projectkoios.ingestion.models import SourceDocument
from projectkoios.ingestion.pdf import PyMuPdfExtractor

pymupdf = pytest.importorskip("pymupdf")


def _fixture_pdf(*, blank_page: bool = True) -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text(
        (72, 72), "1 Introduction\nReusable PDF extraction fixture"
    )
    if blank_page:
        document.new_page()
    content = document.tobytes()
    document.close()
    return content


def _source(content: bytes) -> SourceDocument:
    return SourceDocument.from_bytes(
        content,
        source_id="article:fixture",
        media_type="application/pdf",
        locator="fixture.pdf",
    )


def _extract(content: bytes, **kwargs: int):
    return PyMuPdfExtractor(**kwargs).extract(
        _source(content), BytesIO(content)
    )


def test__pymupdf_extractor__preserves_pages_provenance_and_warnings() -> None:
    content = _fixture_pdf()
    source = _source(content)
    extractor = PyMuPdfExtractor()

    first = extractor.extract(source, BytesIO(content))
    second = extractor.extract(source, BytesIO(content))

    assert len(first.document.pages) == 2
    block = first.document.pages[0].blocks[0]
    assert block.text is not None and "Introduction" in block.text
    assert block.source_spans[0].source_id == "article:fixture"
    assert block.source_spans[0].source_blob_id == source.blob_id
    assert first.manifest.cache_key == second.manifest.cache_key
    assert first.document.document_id == second.document.document_id
    assert {warning.code for warning in first.warnings} == {
        "pdf.low_text_density"
    }


def test__pymupdf_extractor__preserves_printed_page_labels() -> None:
    document = pymupdf.open()
    first_page = document.new_page()
    first_page.insert_text((72, 72), "Printed page label evidence")
    document.new_page()
    document.set_page_labels(
        [{"startpage": 0, "prefix": "A-", "style": "D", "firstpagenum": 7}]
    )
    content = document.tobytes()
    document.close()

    result = _extract(content, low_text_character_threshold=0)

    assert [page.printed_page_label for page in result.document.pages] == [
        "A-7",
        "A-8",
    ]
    assert all(
        block.source_spans[0].printed_page_label
        == result.document.pages[
            block.source_spans[0].page_index
        ].printed_page_label
        for page in result.document.pages
        for block in page.blocks
    )


def test__pymupdf_extractor__emits_content_addressed_image_reference() -> None:
    image = pymupdf.Pixmap(
        pymupdf.csRGB,
        pymupdf.IRect(0, 0, 4, 4),
        False,
    )
    image.clear_with(0x336699)
    document = pymupdf.open()
    page = document.new_page()
    page.insert_image((72, 72, 144, 144), stream=image.tobytes("png"))
    content = document.tobytes()
    document.close()

    first = _extract(content)
    second = _extract(content)
    block = first.document.pages[0].blocks[0]

    assert block.kind == "image"
    assert block.asset_id is not None
    assert block.asset_id.startswith("asset:sha256:")
    assert block.asset_media_type == "image/png"
    assert block.asset_id == second.document.pages[0].blocks[0].asset_id
    assert block.source_spans[0].bounding_box is not None
    assert {warning.code for warning in first.warnings} == {
        "pdf.low_text_density"
    }
    serialized_block = contract_dict(first)["document"]["pages"][0]["blocks"][0]
    assert serialized_block["asset_media_type"] == "image/png"


def test__pymupdf_extractor__identifies_jpeg_image_media_type() -> None:
    image = pymupdf.Pixmap(
        pymupdf.csRGB,
        pymupdf.IRect(0, 0, 4, 4),
        False,
    )
    image.clear_with(0x663399)
    document = pymupdf.open()
    page = document.new_page()
    page.insert_image((72, 72, 144, 144), stream=image.tobytes("jpeg"))
    content = document.tobytes()
    document.close()

    block = _extract(content).document.pages[0].blocks[0]

    assert block.asset_media_type == "image/jpeg"
    assert block.asset_mask_id is None
    assert block.asset_mask_media_type is None


def test__pymupdf_extractor__preserves_image_mask_reference() -> None:
    image = pymupdf.Pixmap(
        pymupdf.csRGB,
        pymupdf.IRect(0, 0, 4, 4),
        True,
    )
    image.clear_with(0x33669980)
    document = pymupdf.open()
    page = document.new_page()
    page.insert_image((72, 72, 144, 144), stream=image.tobytes("png"))
    content = document.tobytes()
    document.close()

    first = _extract(content)
    second = _extract(content)
    block = first.document.pages[0].blocks[0]

    assert block.asset_media_type == "image/png"
    assert block.asset_mask_id is not None
    assert block.asset_mask_id.startswith("asset:sha256:")
    assert block.asset_mask_media_type == "image/png"
    assert block.asset_mask_id == (
        second.document.pages[0].blocks[0].asset_mask_id
    )
    assert serialize_contract(first.document) == serialize_contract(
        second.document
    )


def test__pymupdf_extractor__declares_unrotated_cropbox_coordinates() -> None:
    document = pymupdf.open()
    page = document.new_page(width=612, height=792)
    page.set_cropbox(pymupdf.Rect(50, 100, 550, 700))
    page.insert_text((72, 500), "Unrotated coordinate evidence")
    page.set_rotation(90)
    document.set_toc([[1, "Rotated page", 1]])
    content = document.tobytes()
    document.close()

    result = _extract(content, low_text_character_threshold=0)
    extracted_page = result.document.pages[0]
    bounding_box = extracted_page.blocks[0].source_spans[0].bounding_box
    destination = result.document.table_of_contents[0].destination

    assert (extracted_page.width, extracted_page.height) == (500.0, 600.0)
    assert extracted_page.coordinate_system == (
        "pymupdf_unrotated_cropbox_points_top_left"
    )
    assert bounding_box is not None
    assert bounding_box[2] <= extracted_page.width
    assert bounding_box[3] <= extracted_page.height
    assert destination is not None
    assert destination.bounding_box is not None
    assert destination.bounding_box[2] <= extracted_page.width
    assert destination.bounding_box[3] <= extracted_page.height


def test__pymupdf_extractor__keeps_native_multicolumn_block_order() -> None:
    document = pymupdf.open()
    page = document.new_page(width=600, height=800)
    page.insert_textbox(
        (330, 100, 550, 300),
        "RIGHT ONE\nRIGHT TWO\nRIGHT THREE",
    )
    page.insert_textbox(
        (50, 100, 270, 300),
        "LEFT ONE\nLEFT TWO\nLEFT THREE",
    )
    content = document.tobytes()
    document.close()

    result = _extract(content, low_text_character_threshold=0)
    texts = [block.text for block in result.document.pages[0].blocks]
    warning = result.warnings[0]

    assert texts == [
        "RIGHT ONE\nRIGHT TWO\nRIGHT THREE",
        "LEFT ONE\nLEFT TWO\nLEFT THREE",
    ]
    assert warning.code == "pdf.reading_order_uncertain"
    assert dict(warning.evidence)["block_order"] == "extractor_native"


def test__pymupdf_extractor__extracts_immutable_toc_evidence() -> None:
    document = pymupdf.open()
    document.new_page()
    document.new_page()
    document.set_page_labels(
        [{"startpage": 0, "prefix": "p-", "style": "D", "firstpagenum": 1}]
    )
    document.set_toc(
        [
            [1, "Introduction", 1],
            [2, "Background", 2],
        ]
    )
    content = document.tobytes()
    document.close()

    first = _extract(content, low_text_character_threshold=0)
    second = _extract(content, low_text_character_threshold=0)
    entries = first.document.table_of_contents

    assert [(entry.level, entry.title) for entry in entries] == [
        (1, "Introduction"),
        (2, "Background"),
    ]
    assert entries[1].destination is not None
    assert entries[1].destination.page_index == 1
    assert entries[1].destination.printed_page_label == "p-2"
    assert entries[0].entry_id == second.document.table_of_contents[0].entry_id
    assert entries[0].entry_id in first.manifest.object_ids
    serialized_entry = contract_dict(first)["document"]["table_of_contents"][0]
    assert serialized_entry["title"] == "Introduction"
    with pytest.raises(FrozenInstanceError):
        entries[0].title = "Changed"  # type: ignore[misc]


def test__pymupdf_extractor__configuration_invalidates_cache_identity() -> None:
    content = _fixture_pdf(blank_page=False)
    source = _source(content)
    first_extractor = PyMuPdfExtractor(low_text_character_threshold=0)
    second_extractor = PyMuPdfExtractor(low_text_character_threshold=1)

    first = first_extractor.extract(source, BytesIO(content))
    second = second_extractor.extract(source, BytesIO(content))

    assert first_extractor.cache_key(source) == first.manifest.cache_key
    assert second_extractor.cache_key(source) == second.manifest.cache_key
    assert first.manifest.cache_key != second.manifest.cache_key


def test__pymupdf_extractor__backend_version_invalidates_cache_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = _fixture_pdf(blank_page=False)
    first = _extract(content, low_text_character_threshold=0)
    monkeypatch.setattr(pymupdf, "__version__", "fixture-backend-upgrade")

    second = _extract(content, low_text_character_threshold=0)

    assert first.manifest.extractor_version.endswith(
        f"pymupdf.{importlib.metadata.version('PyMuPDF')}"
    )
    assert second.manifest.extractor_version.endswith(
        "pymupdf.fixture-backend-upgrade"
    )
    assert first.manifest.cache_key != second.manifest.cache_key


def test__pymupdf_extractor__rejects_bytes_from_another_source() -> None:
    content = _fixture_pdf()

    with pytest.raises(ValueError, match="do not agree"):
        PyMuPdfExtractor().extract(
            _source(content), BytesIO(content + b"changed")
        )


def test__pymupdf_extractor__rejects_malformed_pdf() -> None:
    content = b"not a PDF"

    with pytest.raises(pymupdf.FileDataError):
        _extract(content)


def test__pymupdf_extractor__rejects_encrypted_pdf_without_password() -> None:
    document = pymupdf.open()
    document.new_page()
    content = document.tobytes(
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="owner-password",
        user_pw="user-password",
    )
    document.close()

    with pytest.raises(ValueError, match="encrypted PDF requires a password"):
        _extract(content)


def test__cli__publishes_contract_and_raw_pages(tmp_path: Path) -> None:
    pdf = tmp_path / "fixture.pdf"
    output = tmp_path / "artifacts" / "extraction.json"
    pages = tmp_path / "artifacts" / "pages"
    pdf.write_bytes(_fixture_pdf())

    status = main(
        [
            str(pdf),
            "--source-id",
            "article:fixture",
            "--output",
            str(output),
            "--raw-text-directory",
            str(pages),
        ]
    )

    assert status == 0
    assert output.is_file()
    assert (pages / "page-0001.txt").is_file()
    assert (pages / "page-0002.txt").is_file()
    assert '"contract_version":"2.1"' in output.read_text()


def test__cli__cache_hit_avoids_extractor_invocation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf = tmp_path / "fixture.pdf"
    cache = tmp_path / "cache"
    first_output = tmp_path / "first.json"
    second_output = tmp_path / "second.json"
    pdf.write_bytes(_fixture_pdf(blank_page=False))
    arguments = [
        str(pdf),
        "--source-id",
        "article:fixture",
        "--cache-root",
        str(cache),
    ]

    assert main([*arguments, "--output", str(first_output)]) == 0

    def unexpected_extract(*args: object, **kwargs: object) -> None:
        raise AssertionError("extractor invoked for a cache hit")

    monkeypatch.setattr(PyMuPdfExtractor, "extract", unexpected_extract)
    assert main([*arguments, "--output", str(second_output)]) == 0
    assert second_output.read_bytes() == first_output.read_bytes()


def test__cli__excessively_nested_cache_is_a_truthful_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pdf = tmp_path / "fixture.pdf"
    cache_root = tmp_path / "cache"
    first_output = tmp_path / "first.json"
    second_output = tmp_path / "second.json"
    payload = _fixture_pdf(blank_page=False)
    pdf.write_bytes(payload)
    arguments = [
        str(pdf),
        "--source-id",
        "article:fixture",
        "--cache-root",
        str(cache_root),
    ]
    assert main([*arguments, "--output", str(first_output)]) == 0
    source = _source(payload)
    cache_key = PyMuPdfExtractor().cache_key(source)
    key_hash = hashlib.sha256(cache_key.encode()).hexdigest()
    entry = cache_root / "v1" / key_hash[:2] / f"{key_hash}.json"
    depth = max(10_000, sys.getrecursionlimit() * 10)
    entry.write_text("[" * depth + "0" + "]" * depth)

    def unexpected_extract(*args: object, **kwargs: object) -> None:
        raise AssertionError("corruption was treated as a miss")

    monkeypatch.setattr(PyMuPdfExtractor, "extract", unexpected_extract)
    with pytest.raises(SystemExit, match="2"):
        main([*arguments, "--output", str(second_output)])

    assert "extraction cache failure" in capsys.readouterr().err
    assert not second_output.exists()


def test__cli__collision_preflight_leaves_no_new_artifacts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pdf = tmp_path / "fixture.pdf"
    output = tmp_path / "artifacts" / "extraction.json"
    pages = tmp_path / "artifacts" / "pages"
    pdf.write_bytes(_fixture_pdf())
    pages.mkdir(parents=True)
    collision = pages / "page-0002.txt"
    collision.write_text("consumer-owned")

    with pytest.raises(SystemExit, match="2"):
        main(
            [
                str(pdf),
                "--source-id",
                "article:fixture",
                "--output",
                str(output),
                "--raw-text-directory",
                str(pages),
            ]
        )

    assert "refusing to overwrite" in capsys.readouterr().err
    assert collision.read_text() == "consumer-owned"
    assert not output.exists()
    assert not (pages / "page-0001.txt").exists()


def test__cli__handled_mid_publication_error_rolls_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from projectkoios.ingestion import cli

    pdf = tmp_path / "fixture.pdf"
    output = tmp_path / "artifacts" / "extraction.json"
    pages = tmp_path / "artifacts" / "pages"
    pdf.write_bytes(_fixture_pdf())
    original_write = cli._write_new
    calls = 0

    def fail_second_write(path: Path, text: str) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated publication failure")
        original_write(path, text)

    monkeypatch.setattr(cli, "_write_new", fail_second_write)

    with pytest.raises(SystemExit, match="2"):
        main(
            [
                str(pdf),
                "--source-id",
                "article:fixture",
                "--output",
                str(output),
                "--raw-text-directory",
                str(pages),
            ]
        )

    assert "rolled back artifacts created" in capsys.readouterr().err
    assert not output.exists()
    assert not pages.exists()
    assert not (tmp_path / "artifacts").exists()


def test__cli__reports_in_progress_file_cleanup_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "extraction.json"
    original_unlink = Path.unlink

    def fail_output_unlink(
        path: Path,
        missing_ok: bool = False,
    ) -> None:
        if path == output:
            raise OSError("simulated cleanup failure")
        original_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", fail_output_unlink)
    try:
        with pytest.raises(ArtifactPublicationError) as raised:
            _publish_artifacts([(output, "\ud800")])

        assert "rollback incomplete" in str(raised.value)
        assert str(output) in str(raised.value)
        assert output.exists()
    finally:
        if output.exists():
            original_unlink(output)


def test__contract_version__minor_bump_is_explicit() -> None:
    assert CONTRACT_VERSION == "2.1"
