from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import cast

import pytest
from projectkoios.ingestion import (
    OCRConfiguration,
    OCRPageImage,
    OCRRequest,
    OCRResultStatus,
    OCRSelection,
    OCRSelectionStatus,
    PageRegionSelection,
    PyMuPdfRegionRenderer,
    SourceDocument,
    TesseractAdapterConfiguration,
    TesseractLanguageBinding,
    TesseractOCRProcessor,
)
from projectkoios.ingestion.serialization import serialize_contract

_MAX_JSON_BYTES = 64_000_000
_MAX_PDF_BYTES = 1_000_000_000
_CORPUS_ROOT_ENV = "KOIOS_PRIVATE_OCR_PILOT_CORPUS_ROOT"
_OUTPUT_ROOT_ENV = "KOIOS_PRIVATE_OCR_PILOT_OUTPUT_ROOT"
_EXECUTABLE_ENV = "KOIOS_TESSERACT_EXECUTABLE"
_RESOURCE_ENV = "KOIOS_TESSERACT_ENG_TRAINEDDATA"
_SELECTION_POLICY = (
    "one-lowest-empty-page-from-each-of-five-smallest-documents-by-"
    "source-byte-size-then-page-count-then-source-sha;final-order-source-"
    "sha-page-index"
)
_TRANSCRIPT_KEYS = {
    "empty_page_count",
    "extraction_mode",
    "extractor_version",
    "media_type",
    "native_text_page_count",
    "page_count",
    "pages",
    "quality_status",
    "requires_ocr",
    "review_status",
    "source_blob_id",
    "source_byte_size",
    "source_id",
    "source_sha256",
    "status",
    "transcript_id",
}
_PAGE_KEYS = {
    "page_id",
    "physical_page_number",
    "printed_page_label",
    "text",
    "text_sha256",
    "text_utf8_byte_length",
}


@dataclass(frozen=True)
class _PrivatePilotEnvironment:
    corpus_root: Path
    output_root: Path
    executable: Path
    resource: Path


@dataclass(frozen=True)
class _SelectedPage:
    category: str
    document_rank: int
    source_sha256: str
    source_byte_size: int
    source_id: str
    source_blob_id: str
    transcript_id: str
    page_index: int
    page: dict[str, object]
    pdf_path: Path


def _require(condition: bool, code: str) -> None:
    if not condition:
        pytest.fail(
            f"private OCR replay invariant failed: {code}", pytrace=False
        )


def _configured_path(name: str) -> Path | None:
    value = os.environ.get(name)
    return None if value is None else Path(value).expanduser()


@pytest.fixture
def private_ocr_pilot_environment() -> _PrivatePilotEnvironment:
    values = (
        _configured_path(_CORPUS_ROOT_ENV),
        _configured_path(_OUTPUT_ROOT_ENV),
        _configured_path(_EXECUTABLE_ENV),
        _configured_path(_RESOURCE_ENV),
    )
    if any(value is None for value in values):
        pytest.skip("private ten-page OCR replay is not configured")
    corpus_root, output_root, executable, resource = cast(
        tuple[Path, Path, Path, Path], values
    )
    for path in (corpus_root, output_root):
        try:
            metadata = path.lstat()
        except OSError:
            pytest.fail(
                "private OCR replay prerequisite is unavailable",
                pytrace=False,
            )
        _require(
            stat.S_ISDIR(metadata.st_mode)
            and not stat.S_ISLNK(metadata.st_mode),
            "prerequisite-directory",
        )
    try:
        executable_target = executable.resolve(strict=True)
        resource_target = resource.resolve(strict=True)
        executable_metadata = executable_target.lstat()
        resource_metadata = resource_target.lstat()
    except OSError:
        pytest.fail(
            "private OCR replay prerequisite is unavailable",
            pytrace=False,
        )
    _require(
        stat.S_ISREG(executable_metadata.st_mode)
        and stat.S_ISREG(resource_metadata.st_mode),
        "prerequisite-file",
    )
    return _PrivatePilotEnvironment(
        corpus_root=corpus_root,
        output_root=output_root,
        executable=executable_target,
        resource=resource_target,
    )


def _read_exact(path: Path, expected_size: int, maximum: int) -> bytes:
    _require(0 < expected_size <= maximum, "input-size")
    try:
        before = path.lstat()
        _require(
            stat.S_ISREG(before.st_mode) and not stat.S_ISLNK(before.st_mode),
            "input-type",
        )
        _require(before.st_size == expected_size, "input-size-changed")
        with path.open("rb") as stream:
            descriptor = os.fstat(stream.fileno())
            _require(stat.S_ISREG(descriptor.st_mode), "opened-input-type")
            _require(descriptor.st_size == expected_size, "opened-input-size")
            content = stream.read(maximum + 1)
            _require(stream.read(1) == b"", "input-grew-during-read")
        after = path.lstat()
    except OSError:
        pytest.fail("private OCR replay input read failed", pytrace=False)
    _require(len(content) == expected_size, "input-length")
    _require(
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
        "input-changed-during-read",
    )
    return content


def _read_json(path: Path) -> tuple[bytes, object]:
    try:
        metadata = path.lstat()
    except OSError:
        pytest.fail("private OCR replay JSON is unavailable", pytrace=False)
    content = _read_exact(path, metadata.st_size, _MAX_JSON_BYTES)
    try:
        return content, json.loads(content)
    except UnicodeError, json.JSONDecodeError:
        pytest.fail("private OCR replay JSON is malformed", pytrace=False)


def _validated_transcript(
    value: object,
) -> tuple[str, bytes, dict[str, object]] | None:
    if not isinstance(value, dict) or not {
        "source_sha256",
        "source_id",
        "pages",
        "transcript_id",
    }.issubset(value):
        return None
    keys = set(value)
    _require(
        keys in (_TRANSCRIPT_KEYS, _TRANSCRIPT_KEYS | {"fallback_reason"}),
        "transcript-shape",
    )
    transcript = cast(dict[str, object], value)
    source_sha256 = transcript["source_sha256"]
    source_byte_size = transcript["source_byte_size"]
    pages = transcript["pages"]
    _require(
        isinstance(source_sha256, str)
        and len(source_sha256) == 64
        and source_sha256 == source_sha256.lower(),
        "transcript-source-hash",
    )
    try:
        int(source_sha256, 16)
    except ValueError:
        pytest.fail(
            "private OCR replay transcript hash is invalid", pytrace=False
        )
    _require(
        isinstance(source_byte_size, int)
        and not isinstance(source_byte_size, bool)
        and source_byte_size > 0,
        "transcript-source-size",
    )
    _require(isinstance(pages, list) and bool(pages), "transcript-pages")
    _require(
        transcript["source_blob_id"] == f"blob:sha256:{source_sha256}"
        and transcript["page_count"] == len(pages)
        and transcript["media_type"] == "application/pdf"
        and transcript["status"] == "completed"
        and transcript["review_status"] == "automated_unreviewed",
        "transcript-identity",
    )

    page_ids: list[str] = []
    empty_count = 0
    native_count = 0
    for page_index, raw_page in enumerate(pages):
        _require(
            isinstance(raw_page, dict) and set(raw_page) == _PAGE_KEYS,
            "transcript-page-shape",
        )
        page = cast(dict[str, object], raw_page)
        text = page["text"]
        _require(isinstance(text, str), "transcript-page-text-type")
        encoded = text.encode("utf-8", errors="strict")
        _require(
            page["physical_page_number"] == page_index + 1
            and page["text_utf8_byte_length"] == len(encoded)
            and page["text_sha256"] == hashlib.sha256(encoded).hexdigest(),
            "transcript-page-hash",
        )
        page_id = page["page_id"]
        _require(
            isinstance(page_id, str) and bool(page_id),
            "transcript-page-id",
        )
        page_ids.append(page_id)
        empty_count += int(text == "")
        native_count += int(text != "")
    _require(
        len(page_ids) == len(set(page_ids))
        and empty_count == transcript["empty_page_count"]
        and native_count == transcript["native_text_page_count"]
        and transcript["requires_ocr"] is (empty_count > 0),
        "transcript-page-counts",
    )
    signature = json.dumps(
        transcript,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return source_sha256, signature, transcript


def _discover_selection(
    environment: _PrivatePilotEnvironment,
) -> tuple[_SelectedPage, ...]:
    pdfs: dict[tuple[str, int], list[Path]] = {}
    transcripts: dict[str, tuple[bytes, dict[str, object]]] = {}
    excluded_output = environment.output_root.resolve()

    for base, directories, names in os.walk(
        environment.corpus_root,
        topdown=True,
        followlinks=False,
    ):
        base_path = Path(base)
        safe_directories = []
        for name in sorted(directories):
            child = base_path / name
            if child.is_symlink() or child.resolve() == excluded_output:
                continue
            safe_directories.append(name)
        directories[:] = safe_directories
        for name in sorted(names):
            path = base_path / name
            try:
                metadata = path.lstat()
            except OSError:
                pytest.fail(
                    "private OCR corpus traversal failed", pytrace=False
                )
            if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(
                metadata.st_mode
            ):
                continue
            if path.suffix.lower() == ".pdf":
                content = _read_exact(path, metadata.st_size, _MAX_PDF_BYTES)
                digest = hashlib.sha256(content).hexdigest()
                pdfs.setdefault((digest, metadata.st_size), []).append(path)
            elif (
                path.suffix.lower() == ".json"
                and 0 < metadata.st_size <= _MAX_JSON_BYTES
            ):
                _, value = _read_json(path)
                validated = _validated_transcript(value)
                if validated is None:
                    continue
                digest, signature, transcript = validated
                previous = transcripts.get(digest)
                _require(
                    previous is None or previous[0] == signature,
                    "conflicting-transcripts",
                )
                transcripts[digest] = (signature, transcript)

    all_empty: list[tuple[object, ...]] = []
    partially_native: list[tuple[object, ...]] = []
    for source_sha256, (_, transcript) in transcripts.items():
        source_byte_size = cast(int, transcript["source_byte_size"])
        pages = cast(list[dict[str, object]], transcript["pages"])
        matches = pdfs.get((source_sha256, source_byte_size))
        _require(bool(matches), "transcript-source-unmatched")
        safe_matches = cast(list[Path], matches)
        pdf_path = sorted(
            safe_matches,
            key=lambda item: item.relative_to(
                environment.corpus_root
            ).as_posix(),
        )[0]
        empty_pages = tuple(
            index for index, page in enumerate(pages) if page["text"] == ""
        )
        row = (
            source_byte_size,
            len(pages),
            source_sha256,
            transcript,
            pdf_path,
            empty_pages,
        )
        if len(empty_pages) == len(pages):
            all_empty.append(row)
        elif empty_pages:
            partially_native.append(row)

    all_empty.sort(key=lambda row: row[:3])
    partially_native.sort(key=lambda row: row[:3])
    _require(
        len(all_empty) >= 5 and len(partially_native) >= 5,
        "insufficient-selection",
    )
    selected: list[_SelectedPage] = []
    for category, rows in (
        ("all_empty", all_empty[:5]),
        ("partially_native", partially_native[:5]),
    ):
        for document_rank, row in enumerate(rows, 1):
            (
                source_byte_size,
                _,
                source_sha256,
                raw_transcript,
                pdf_path,
                empty_pages,
            ) = row
            transcript = cast(dict[str, object], raw_transcript)
            pages = cast(list[dict[str, object]], transcript["pages"])
            page_index = cast(tuple[int, ...], empty_pages)[0]
            selected.append(
                _SelectedPage(
                    category=category,
                    document_rank=document_rank,
                    source_sha256=cast(str, source_sha256),
                    source_byte_size=cast(int, source_byte_size),
                    source_id=cast(str, transcript["source_id"]),
                    source_blob_id=cast(str, transcript["source_blob_id"]),
                    transcript_id=cast(str, transcript["transcript_id"]),
                    page_index=page_index,
                    page=pages[page_index],
                    pdf_path=cast(Path, pdf_path),
                )
            )
    selected.sort(key=lambda item: (item.source_sha256, item.page_index))
    _require(
        len(selected) == 10
        and len({(item.source_sha256, item.page_index) for item in selected})
        == 10,
        "selection-count",
    )
    return tuple(selected)


def _selection_manifest(
    selected: tuple[_SelectedPage, ...],
) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            item.category,
            item.document_rank,
            item.source_sha256,
            item.source_byte_size,
            item.source_id,
            item.source_blob_id,
            item.transcript_id,
            item.page_index,
            item.page["page_id"],
            item.page["text_sha256"],
            item.page["text_utf8_byte_length"],
        )
        for item in selected
    )


def _expected_manifest(records: object) -> tuple[tuple[object, ...], ...]:
    _require(isinstance(records, list), "expected-records-type")
    result = []
    for record in records:
        _require(isinstance(record, dict), "expected-record-shape")
        item = cast(dict[str, object], record)
        result.append(
            (
                item.get("category"),
                item.get("document_rank"),
                item.get("source_sha256"),
                item.get("source_byte_size"),
                item.get("source_id"),
                item.get("source_blob_id"),
                item.get("transcript_id"),
                item.get("page_index"),
                item.get("page_id"),
                item.get("native_text_sha256"),
                item.get("native_text_utf8_byte_length"),
            )
        )
    return tuple(result)


@pytest.mark.private_integration
def test__private_ten_page_ocr_replay__matches_published_evidence(
    private_ocr_pilot_environment: _PrivatePilotEnvironment,
) -> None:
    environment = private_ocr_pilot_environment
    stage = "expected-evidence"
    try:
        _, expected_value = _read_json(environment.output_root / "summary.json")
        _require(isinstance(expected_value, dict), "expected-summary-shape")
        expected = cast(dict[str, object], expected_value)
        _require(
            expected.get("status") == "completed_deterministic"
            and expected.get("selection_policy") == _SELECTION_POLICY
            and expected.get("selection_count") == 10
            and expected.get("executions_per_selection") == 2,
            "expected-summary-identity",
        )

        stage = "selection"
        selected = _discover_selection(environment)
        _require(
            _selection_manifest(selected)
            == _expected_manifest(expected.get("records")),
            "selection-mismatch",
        )

        stage = "tool-evidence"
        executable_metadata = environment.executable.lstat()
        resource_metadata = environment.resource.lstat()
        executable_before = hashlib.sha256(
            _read_exact(
                environment.executable,
                executable_metadata.st_size,
                256_000_000,
            )
        ).hexdigest()
        resource_before = hashlib.sha256(
            _read_exact(
                environment.resource,
                resource_metadata.st_size,
                256_000_000,
            )
        ).hexdigest()
        expected_executable = expected.get("executable")
        expected_resource = expected.get("language_resource")
        _require(
            isinstance(expected_executable, dict)
            and executable_before == expected_executable.get("sha256"),
            "executable-hash",
        )
        _require(
            isinstance(expected_resource, dict)
            and resource_before == expected_resource.get("sha256"),
            "resource-hash",
        )

        renderer = PyMuPdfRegionRenderer(resolution_dpi=300)
        adapter_configuration = TesseractAdapterConfiguration()
        ocr_configuration = OCRConfiguration(languages=("en",))
        processor = TesseractOCRProcessor(
            executable=environment.executable,
            language_bindings=(
                TesseractLanguageBinding(
                    language="en",
                    resource_name="eng",
                    traineddata_path=environment.resource,
                ),
            ),
            configuration=adapter_configuration,
        )
        expected_configuration = expected.get("configuration")
        _require(
            isinstance(expected_configuration, dict)
            and renderer.configuration_digest
            == expected_configuration.get("renderer_digest")
            and adapter_configuration.configuration_digest
            == expected_configuration.get("tesseract_adapter_digest")
            and ocr_configuration.configuration_digest
            == expected_configuration.get("ocr_digest"),
            "configuration-digest",
        )

        stage = "replay"
        deterministic_result_digests: list[str] = []
        completed = 0
        warning_count = 0
        for item in selected:
            content = _read_exact(
                item.pdf_path,
                item.source_byte_size,
                _MAX_PDF_BYTES,
            )
            _require(
                hashlib.sha256(content).hexdigest() == item.source_sha256,
                "selected-source-hash",
            )
            source = SourceDocument.from_bytes(
                content,
                source_id=item.source_id,
                media_type="application/pdf",
                locator=("private-ocr-pilot:sha256:" + item.source_sha256),
            )
            _require(
                source.blob_id == item.source_blob_id
                and source.content_hash == item.source_sha256
                and source.byte_length == item.source_byte_size,
                "source-identity",
            )
            page_selection = PageRegionSelection.for_full_page(
                source, item.page_index
            )
            first_region = renderer.render(
                source,
                BytesIO(content),
                (page_selection,),
            )[0]
            second_region = renderer.render(
                source,
                BytesIO(content),
                (page_selection,),
            )[0]
            _require(
                first_region == second_region
                and first_region.content == second_region.content,
                "render-determinism",
            )
            image = OCRPageImage.from_rendered_region(first_region)
            selection = OCRSelection.create(image)
            request = OCRRequest.create(
                (selection,), configuration=ocr_configuration
            )
            processor_identity = processor.identity_for(request)
            first = processor.action(request=request)
            first_bytes = serialize_contract(first).encode("utf-8")
            second = processor.action(request=request)
            second_bytes = serialize_contract(second).encode("utf-8")
            _require(
                first == second and first_bytes == second_bytes,
                "ocr-determinism",
            )
            _require(
                first.processor_identity == processor_identity
                and len(first.selection_results) == 1,
                "ocr-result-identity",
            )
            selection_result = first.selection_results[0]
            _require(
                first.status is OCRResultStatus.COMPLETED
                and selection_result.status is OCRSelectionStatus.COMPLETED
                and selection_result.failure is None,
                "ocr-status",
            )
            warning_count += len(selection_result.warnings)
            completed += 1
            deterministic_result_digests.append(
                hashlib.sha256(first_bytes).hexdigest()
            )

        stage = "aggregate"
        aggregate_digest = hashlib.sha256(
            json.dumps(
                deterministic_result_digests,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        expected_aggregate = expected.get("aggregate_ocr_evidence_sha256")
        expected_records = cast(list[dict[str, object]], expected["records"])
        expected_result_digests = [
            cast(dict[str, object], record["ocr_evidence"]).get(
                "canonical_result_sha256"
            )
            for record in expected_records
        ]
        _require(completed == 10, "completed-count")
        _require(warning_count == 0, "warning-count")
        _require(
            deterministic_result_digests == expected_result_digests,
            "result-evidence-digests",
        )
        _require(
            isinstance(expected_aggregate, str)
            and aggregate_digest == expected_aggregate,
            "aggregate-evidence-digest",
        )

        stage = "postflight"
        executable_after = hashlib.sha256(
            _read_exact(
                environment.executable,
                executable_metadata.st_size,
                256_000_000,
            )
        ).hexdigest()
        resource_after = hashlib.sha256(
            _read_exact(
                environment.resource,
                resource_metadata.st_size,
                256_000_000,
            )
        ).hexdigest()
        _require(
            executable_after == executable_before
            and resource_after == resource_before,
            "tool-evidence-changed",
        )
    except pytest.skip.Exception:
        raise
    except pytest.fail.Exception:
        raise
    except Exception as error:
        pytest.fail(
            f"private OCR replay failed at {stage}: {type(error).__name__}",
            pytrace=False,
        )
