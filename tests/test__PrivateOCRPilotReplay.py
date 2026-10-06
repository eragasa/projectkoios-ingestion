from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import cast

import pytest
from projectkoios.ingestion import (
    PageRegionSelection,
    SourceDocument,
    TesseractAdapterConfiguration,
    TesseractLanguageBinding,
    TesseractOCRProcessor,
)
from projectkoios.ingestion.ocr.configuration import OCRConfiguration
from projectkoios.ingestion.ocr.page_image import OCRPageImage
from projectkoios.ingestion.ocr.request import OCRRequest
from projectkoios.ingestion.ocr.result_status import OCRResultStatus
from projectkoios.ingestion.ocr.selection import OCRSelection
from projectkoios.ingestion.ocr.selection_status import OCRSelectionStatus
from projectkoios.ingestion.pdf.adapters.pymupdf.rendering import (
    PyMuPdfRegionRenderer,
)
from projectkoios.ingestion.serialization import serialize_contract
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.verifier import SHA256Verifier

_MAX_JSON_BYTES = 64_000_000
_MAX_PDF_BYTES = 1_000_000_000
_MAX_TOOL_BYTES = 256_000_000
_CORPUS_ROOT_ENV = "KOIOS_PRIVATE_OCR_PILOT_CORPUS_ROOT"
_EXECUTABLE_ENV = "KOIOS_TESSERACT_EXECUTABLE"
_RESOURCE_ENV = "KOIOS_TESSERACT_ENG_TRAINEDDATA"


@dataclass(frozen=True)
class _PrivatePilotEnvironment:
    corpus_root: Path
    executable: Path
    resource: Path


@dataclass(frozen=True)
class _SelectedPage:
    source_sha256: str
    source_byte_size: int
    source_id: str
    page_count: int
    page_index: int
    pdf_path: Path


@dataclass(frozen=True)
class _PipelineEvidence:
    result_digests: tuple[str, ...]
    aggregate_digest: str
    completed: int
    warning_count: int


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
        _configured_path(_EXECUTABLE_ENV),
        _configured_path(_RESOURCE_ENV),
    )
    if any(value is None for value in values):
        pytest.skip("private ten-page OCR replay is not configured")
    corpus_root, executable, resource = cast(tuple[Path, Path, Path], values)
    try:
        corpus_metadata = corpus_root.lstat()
        executable_target = executable.resolve(strict=True)
        resource_target = resource.resolve(strict=True)
        executable_metadata = executable_target.lstat()
        resource_metadata = resource_target.lstat()
    except OSError:
        pytest.fail(
            "private OCR replay prerequisite is unavailable", pytrace=False
        )
    _require(
        stat.S_ISDIR(corpus_metadata.st_mode)
        and not stat.S_ISLNK(corpus_metadata.st_mode),
        "corpus-root",
    )
    _require(
        stat.S_ISREG(executable_metadata.st_mode)
        and stat.S_ISREG(resource_metadata.st_mode),
        "tool-resource-type",
    )
    return _PrivatePilotEnvironment(
        corpus_root=corpus_root,
        executable=executable_target,
        resource=resource_target,
    )


def _read_bounded(path: Path, maximum: int) -> bytes:
    metadata = path.lstat()
    _require(
        stat.S_ISREG(metadata.st_mode)
        and not stat.S_ISLNK(metadata.st_mode)
        and 0 < metadata.st_size <= maximum,
        "bounded-input",
    )
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        _require(
            stat.S_ISREG(opened.st_mode) and opened.st_size == metadata.st_size,
            "opened-input",
        )
        content = stream.read(maximum + 1)
    _require(len(content) == metadata.st_size, "input-length")
    return content


def _is_sha256(value: str) -> bool:
    if len(value) != 64 or value != value.lower():
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _selection_candidates(
    corpus_root: Path,
) -> tuple[list[_SelectedPage], list[_SelectedPage]]:
    all_empty: list[_SelectedPage] = []
    partially_native: list[_SelectedPage] = []
    for directory in sorted(corpus_root.iterdir(), key=lambda item: item.name):
        if (
            not directory.is_dir()
            or directory.is_symlink()
            or not _is_sha256(directory.name)
        ):
            continue
        transcript_path = directory / "transcript.json"
        pdf_path = directory / "document.pdf"
        _require(
            transcript_path.is_file() and pdf_path.is_file(),
            "processed-reference-members",
        )
        value = json.loads(_read_bounded(transcript_path, _MAX_JSON_BYTES))
        _require(isinstance(value, dict), "transcript-object")
        transcript = cast(dict[str, object], value)
        source_byte_size = transcript.get("source_byte_size")
        source_id = transcript.get("source_id")
        page_count = transcript.get("page_count")
        empty_page_count = transcript.get("empty_page_count")
        native_text_page_count = transcript.get("native_text_page_count")
        raw_pages = transcript.get("pages")
        _require(
            transcript.get("source_sha256") == directory.name
            and isinstance(source_byte_size, int)
            and not isinstance(source_byte_size, bool)
            and source_byte_size > 0
            and isinstance(source_id, str)
            and bool(source_id)
            and isinstance(page_count, int)
            and not isinstance(page_count, bool)
            and page_count > 0
            and isinstance(empty_page_count, int)
            and isinstance(native_text_page_count, int)
            and isinstance(raw_pages, list)
            and len(raw_pages) == page_count,
            "selection-fields",
        )
        if empty_page_count == 0:
            continue
        pages = cast(list[object], raw_pages)
        empty_indices = tuple(
            index
            for index, page in enumerate(pages)
            if isinstance(page, dict) and page.get("text") == ""
        )
        _require(
            len(empty_indices) == empty_page_count,
            "empty-page-count",
        )
        page_index = empty_indices[0]
        page = cast(dict[str, object], pages[page_index])
        _require(
            SHA256Verifier.verify(
                content=b"", expected=page.get("text_sha256")
            ),
            "selected-page-hash",
        )
        candidate = _SelectedPage(
            source_sha256=directory.name,
            source_byte_size=source_byte_size,
            source_id=source_id,
            page_count=page_count,
            page_index=page_index,
            pdf_path=pdf_path,
        )
        if empty_page_count == page_count and native_text_page_count == 0:
            all_empty.append(candidate)
        elif (
            0 < empty_page_count < page_count
            and native_text_page_count == page_count - empty_page_count
        ):
            partially_native.append(candidate)

    def ranking(item: _SelectedPage) -> tuple[int, int, str]:
        return (
            item.source_byte_size,
            item.page_count,
            item.source_sha256,
        )

    all_empty.sort(key=ranking)
    partially_native.sort(key=ranking)
    return all_empty, partially_native


def _select_pages(corpus_root: Path) -> tuple[_SelectedPage, ...]:
    all_empty, partially_native = _selection_candidates(corpus_root)
    _require(
        len(all_empty) >= 5 and len(partially_native) >= 5,
        "selection-population",
    )
    selected = all_empty[:5] + partially_native[:5]
    selected.sort(key=lambda item: (item.source_sha256, item.page_index))
    _require(
        len(selected) == 10
        and len({(item.source_sha256, item.page_index) for item in selected})
        == 10,
        "selection-count",
    )
    return tuple(selected)


def _run_pipeline(
    selected: tuple[_SelectedPage, ...],
    *,
    renderer: PyMuPdfRegionRenderer,
    processor: TesseractOCRProcessor,
    ocr_configuration: OCRConfiguration,
) -> _PipelineEvidence:
    result_digests: list[str] = []
    completed = 0
    warning_count = 0
    for item in selected:
        content = _read_bounded(item.pdf_path, _MAX_PDF_BYTES)
        _require(
            len(content) == item.source_byte_size
            and SHA256Verifier.verify(
                content=content, expected=item.source_sha256
            ),
            "selected-pdf-hash",
        )
        source = SourceDocument.from_bytes(
            content,
            source_id=item.source_id,
            media_type="application/pdf",
            locator="private-ocr-pilot:sha256:" + item.source_sha256,
        )
        region = renderer.render(
            source,
            BytesIO(content),
            (PageRegionSelection.for_full_page(source, item.page_index),),
        )[0]
        image = OCRPageImage.from_rendered_region(region)
        request = OCRRequest.create(
            (OCRSelection.create(image),),
            configuration=ocr_configuration,
        )
        result = processor.action(request=request)
        _require(
            result.status is OCRResultStatus.COMPLETED
            and len(result.selection_results) == 1,
            "ocr-result",
        )
        selection_result = result.selection_results[0]
        _require(
            selection_result.status is OCRSelectionStatus.COMPLETED
            and selection_result.failure is None,
            "ocr-selection-result",
        )
        completed += 1
        warning_count += len(selection_result.warnings)
        result_digests.append(
            SHA256Fingerprinter.fingerprint(
                content=serialize_contract(result).encode("utf-8")
            )
        )
    aggregate_digest = SHA256Fingerprinter.fingerprint(
        content=json.dumps(result_digests, separators=(",", ":")).encode(
            "utf-8"
        )
    )
    return _PipelineEvidence(
        result_digests=tuple(result_digests),
        aggregate_digest=aggregate_digest,
        completed=completed,
        warning_count=warning_count,
    )


@pytest.mark.private_integration
def test__private_ten_page_ocr_replay__is_deterministic(
    private_ocr_pilot_environment: _PrivatePilotEnvironment,
) -> None:
    environment = private_ocr_pilot_environment
    stage = "selection"
    try:
        selected = _select_pages(environment.corpus_root)
        executable_before = SHA256Fingerprinter.fingerprint(
            content=_read_bounded(environment.executable, _MAX_TOOL_BYTES)
        )
        resource_before = SHA256Fingerprinter.fingerprint(
            content=_read_bounded(environment.resource, _MAX_TOOL_BYTES)
        )
        renderer = PyMuPdfRegionRenderer(resolution_dpi=300)
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
            configuration=TesseractAdapterConfiguration(),
        )

        stage = "first-pipeline"
        first = _run_pipeline(
            selected,
            renderer=renderer,
            processor=processor,
            ocr_configuration=ocr_configuration,
        )
        stage = "second-pipeline"
        second = _run_pipeline(
            selected,
            renderer=renderer,
            processor=processor,
            ocr_configuration=ocr_configuration,
        )
        stage = "comparison"
        _require(first.completed == second.completed == 10, "completed-count")
        _require(
            first.warning_count == second.warning_count == 0,
            "warning-count",
        )
        _require(
            first.result_digests == second.result_digests,
            "result-digests",
        )
        _require(
            first.aggregate_digest == second.aggregate_digest,
            "aggregate-digest",
        )
        _require(
            SHA256Verifier.verify(
                content=_read_bounded(environment.executable, _MAX_TOOL_BYTES),
                expected=executable_before,
            )
            and SHA256Verifier.verify(
                content=_read_bounded(environment.resource, _MAX_TOOL_BYTES),
                expected=resource_before,
            ),
            "tool-resource-changed",
        )
    except pytest.fail.Exception:
        raise
    except Exception as error:
        pytest.fail(
            f"private OCR replay failed at {stage}: {type(error).__name__}",
            pytrace=False,
        )
