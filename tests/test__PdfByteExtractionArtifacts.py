from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from io import BytesIO
from pathlib import Path

import pytest
from projectkoios.ingestion import (
    RAW_EXTRACTION_RELATIVE_PATH,
    PdfExtractionArtifactBundle,
    PdfExtractionArtifactLimitError,
    PdfExtractionArtifactLimits,
    PdfExtractionArtifactValidationError,
    PdfExtractionConfiguration,
    PdfPageLimitError,
    PdfSourceIntegrityError,
    PyMuPdfExtractor,
    SourceDocument,
    build_pdf_extraction_artifacts,
    extract_pdf_bytes_artifacts,
)
from projectkoios.ingestion.cli import ingest_pdf_artifacts
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.pdf import artifacts as artifact_module
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.verifier import SHA256Verifier

pymupdf = pytest.importorskip("pymupdf")


def _pdf(page_count: int = 2) -> bytes:
    document = pymupdf.open()
    for index in range(page_count):
        page = document.new_page()
        page.insert_text((72, 72), f"Page {index + 1} exact text")
    content = bytes(document.tobytes())
    document.close()
    return content


def _extract(
    content: bytes, *, maximum_pages: int = 2
) -> PdfExtractionArtifactBundle:
    return extract_pdf_bytes_artifacts(
        content,
        source_id="article:bytes-fixture",
        locator="staged/fixture.pdf",
        low_text_character_threshold=0,
        expected_source_sha256=SHA256Fingerprinter.fingerprint(content=content),
        expected_source_byte_size=len(content),
        maximum_pages=maximum_pages,
    )


def test__byte_api_returns_owner_built_bounded_artifacts_without_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = _pdf()
    monkeypatch.chdir(tmp_path)

    bundle = _extract(content)

    assert list(tmp_path.iterdir()) == []
    assert bundle.result.manifest.configuration_digest == (
        bundle.configuration.configuration_digest
    )
    assert bundle.configuration.maximum_pages == 2
    assert tuple(item.relative_path for item in bundle.artifacts) == (
        "raw-extraction.json",
        "raw-pages/page-0001.txt",
        "raw-pages/page-0002.txt",
    )
    assert (
        bundle.artifacts[0].content
        == (
            CanonicalJsonSerializer.serialize_text(bundle.result) + "\n"
        ).encode()
    )
    assert b"Page 1 exact text" in bundle.artifacts[1].content
    assert b"Page 2 exact text" in bundle.artifacts[2].content
    for artifact in bundle.artifacts:
        assert artifact.byte_length == len(artifact.content)
        assert SHA256Verifier.verify(
            content=artifact.content, expected=artifact.content_sha256
        )


def test__page_limit_fails_typed_before_artifact_creation_or_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = _pdf(2)
    monkeypatch.chdir(tmp_path)

    def unexpected_artifact_creation(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("artifact creation must not run")

    def unexpected_page_load(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("page loading must not run")

    monkeypatch.setattr(
        artifact_module, "_artifact_payloads", unexpected_artifact_creation
    )
    monkeypatch.setattr(pymupdf.Document, "load_page", unexpected_page_load)

    with pytest.raises(PdfPageLimitError) as raised:
        _extract(content, maximum_pages=1)

    assert raised.value.page_count == 2
    assert raised.value.maximum_pages == 1
    assert list(tmp_path.iterdir()) == []


def test__incoherent_page_and_artifact_bounds_fail_before_page_loading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = _pdf(1)

    def unexpected_page_load(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("page loading must not run")

    monkeypatch.setattr(pymupdf.Document, "load_page", unexpected_page_load)

    with pytest.raises(PdfExtractionArtifactLimitError, match="incoherent"):
        extract_pdf_bytes_artifacts(
            content,
            source_id="article:incoherent-bounds",
            locator="staged/incoherent.pdf",
            low_text_character_threshold=0,
            expected_source_sha256=SHA256Fingerprinter.fingerprint(
                content=content
            ),
            expected_source_byte_size=len(content),
            maximum_pages=2,
            artifact_limits=PdfExtractionArtifactLimits(max_artifacts=1),
        )


def test__cli_page_limit_leaves_no_output_artifacts(tmp_path: Path) -> None:
    content = _pdf(2)
    source = tmp_path / "fixture.pdf"
    output = tmp_path / "out/raw-extraction.json"
    raw_pages = tmp_path / "out/raw-pages"
    source.write_bytes(content)

    with pytest.raises(PdfPageLimitError):
        ingest_pdf_artifacts(
            source,
            source_id="article:cli-limit",
            output=output,
            raw_text_directory=raw_pages,
            expected_source_sha256=SHA256Fingerprinter.fingerprint(
                content=content
            ),
            expected_source_byte_size=len(content),
            maximum_pages=1,
        )

    assert not output.exists()
    assert not raw_pages.exists()


@pytest.mark.parametrize("mismatch", ["hash", "size"])
def test__byte_api_rejects_source_identity_mismatch_before_extraction(
    mismatch: str,
) -> None:
    content = _pdf(1)
    digest = SHA256Fingerprinter.fingerprint(content=content)
    size = len(content)
    if mismatch == "hash":
        digest = "0" * 64
    else:
        size += 1

    with pytest.raises(PdfSourceIntegrityError):
        extract_pdf_bytes_artifacts(
            content,
            source_id="article:mismatch",
            locator="staged/mismatch.pdf",
            low_text_character_threshold=0,
            expected_source_sha256=digest,
            expected_source_byte_size=size,
            maximum_pages=1,
        )


def test__extractor_behavior_is_read_only_and_aligned_with_identity() -> None:
    one_page = _pdf(1)
    source = SourceDocument.from_bytes(
        one_page,
        source_id="article:read-only-configuration",
        media_type="application/pdf",
        locator="memory://read-only.pdf",
    )
    extractor = PyMuPdfExtractor(
        low_text_character_threshold=0,
        maximum_pages=1,
    )

    with pytest.raises(AttributeError):
        extractor.maximum_pages = 2  # type: ignore[misc]
    with pytest.raises(AttributeError):
        extractor.low_text_character_threshold = 100  # type: ignore[misc]

    result = extractor.extract(source, BytesIO(one_page))

    assert extractor.maximum_pages == extractor.configuration.maximum_pages
    assert extractor.low_text_character_threshold == (
        extractor.configuration.low_text_character_threshold
    )
    assert result.manifest.configuration_digest == (
        extractor.configuration.configuration_digest
    )
    assert result.manifest.cache_key == extractor.cache_key(source)
    assert result.warnings == ()

    two_pages = _pdf(2)
    two_page_source = SourceDocument.from_bytes(
        two_pages,
        source_id="article:read-only-limit",
        media_type="application/pdf",
        locator="memory://read-only-limit.pdf",
    )
    with pytest.raises(PdfPageLimitError):
        extractor.extract(two_page_source, BytesIO(two_pages))


def test__maximum_pages_changes_extractor_and_manifest_identity() -> None:
    content = _pdf(1)
    first = _extract(content, maximum_pages=1)
    second = _extract(content, maximum_pages=2)

    assert first.configuration.configuration_digest != (
        second.configuration.configuration_digest
    )
    assert first.result.manifest.configuration_digest != (
        second.result.manifest.configuration_digest
    )
    assert first.result.manifest.cache_key != second.result.manifest.cache_key
    assert PyMuPdfExtractor(maximum_pages=1).configuration_digest != (
        PyMuPdfExtractor(maximum_pages=2).configuration_digest
    )


def test__semantic_output_and_artifact_shape_are_repeatable() -> None:
    content = _pdf(2)
    first = _extract(content)
    second = _extract(content)
    rebuilt = build_pdf_extraction_artifacts(
        first.result,
        configuration=first.configuration,
        artifact_limits=first.artifact_limits,
    )

    assert CanonicalJsonSerializer.serialize_text(
        first.result.document
    ) == CanonicalJsonSerializer.serialize_text(second.result.document)
    assert tuple(
        (item.relative_path, item.media_type) for item in first.artifacts
    ) == tuple(
        (item.relative_path, item.media_type) for item in second.artifacts
    )
    assert first.artifacts[1:] == second.artifacts[1:]
    assert rebuilt == first


def test__artifact_limits_are_enforced() -> None:
    content = _pdf(2)
    bundle = _extract(content)

    with pytest.raises(PdfExtractionArtifactLimitError, match="count"):
        build_pdf_extraction_artifacts(
            bundle.result,
            configuration=bundle.configuration,
            artifact_limits=PdfExtractionArtifactLimits(max_artifacts=2),
        )
    with pytest.raises(PdfExtractionArtifactLimitError, match="page text"):
        build_pdf_extraction_artifacts(
            bundle.result,
            configuration=bundle.configuration,
            artifact_limits=PdfExtractionArtifactLimits(max_page_text_bytes=8),
        )
    with pytest.raises(PdfExtractionArtifactLimitError, match="JSON"):
        build_pdf_extraction_artifacts(
            bundle.result,
            configuration=bundle.configuration,
            artifact_limits=PdfExtractionArtifactLimits(
                max_raw_extraction_bytes=1
            ),
        )


def test__direct_construction_rejects_artifact_and_bundle_tampering() -> None:
    content = _pdf(2)
    bundle = _extract(content)
    raw = bundle.artifacts[0]

    with pytest.raises(PdfExtractionArtifactValidationError, match="canonical"):
        replace(raw, relative_path="../raw-extraction.json")
    with pytest.raises(PdfExtractionArtifactValidationError, match="hash"):
        replace(raw, content_sha256="0" * 64)
    with pytest.raises(PdfExtractionArtifactValidationError, match="canonical"):
        replace(bundle, artifacts=tuple(reversed(bundle.artifacts)))
    with pytest.raises(
        PdfExtractionArtifactValidationError, match="configuration"
    ):
        replace(
            bundle,
            configuration=PdfExtractionConfiguration(
                low_text_character_threshold=0,
                maximum_pages=3,
            ),
        )
    with pytest.raises(PdfExtractionArtifactValidationError, match="identity"):
        replace(
            bundle,
            bundle_id="pdf-extraction-artifact-bundle:sha256:" + "0" * 64,
        )
    with pytest.raises(FrozenInstanceError):
        raw.relative_path = "changed"  # type: ignore[misc]


def test__byte_api_requires_immutable_bytes_and_bounded_maximum_pages() -> None:
    content = _pdf(1)
    digest = SHA256Fingerprinter.fingerprint(content=content)

    with pytest.raises(TypeError, match="immutable bytes"):
        extract_pdf_bytes_artifacts(
            bytearray(content),  # type: ignore[arg-type]
            source_id="article:type",
            locator="staged/type.pdf",
            low_text_character_threshold=0,
            expected_source_sha256=digest,
            expected_source_byte_size=len(content),
            maximum_pages=1,
        )
    with pytest.raises(ValueError, match="maximum_pages"):
        extract_pdf_bytes_artifacts(
            content,
            source_id="article:type",
            locator="staged/type.pdf",
            low_text_character_threshold=0,
            expected_source_sha256=digest,
            expected_source_byte_size=len(content),
            maximum_pages=True,
        )


def test__artifact_paths_are_canonical_relative_posix_paths() -> None:
    bundle = _extract(_pdf(1), maximum_pages=1)

    assert bundle.artifacts[0].relative_path == RAW_EXTRACTION_RELATIVE_PATH
    assert all(
        not item.relative_path.startswith("/")
        and ".." not in item.relative_path.split("/")
        and "\\" not in item.relative_path
        for item in bundle.artifacts
    )
