from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from projectkoios.ingestion.batch import PdfBatchItem, PdfBatchPlan
from projectkoios.ingestion.cache import deserialize_extraction_result
from projectkoios.ingestion.models import ExtractionResult
from projectkoios.ingestion.pdf import (
    RAW_EXTRACTION_MEDIA_TYPE,
    RAW_EXTRACTION_RELATIVE_PATH,
    RAW_PAGE_TEXT_MEDIA_TYPE,
    PdfExtractionArtifactLimits,
    PdfExtractionArtifactPayload,
    PdfExtractionConfiguration,
    PdfExtractionTranscript,
    build_pdf_extraction_artifacts,
    read_pdf_extraction_transcript,
)

_MAX_BATCH_ITEMS = 256
_MAX_PLAN_BYTES = 4_000_000
_MAX_PLAN_FILES = 10_000
_MAX_SOURCE_BYTES = 512_000_000
_MAX_TOTAL_SOURCE_BYTES = 10_000_000_000
_PLAN_NAME = re.compile(r"batch-[0-9]{5}\.json")


class PdfCorpusError(ValueError):
    """Base error for bounded PDF corpus preparation and validation."""


class PdfCorpusPublicationError(RuntimeError):
    """Raised when an immutable corpus plan set cannot be published."""


@dataclass(frozen=True)
class PdfCorpusLimits:
    max_files: int = _MAX_PLAN_FILES
    max_file_bytes: int = _MAX_SOURCE_BYTES
    max_total_bytes: int = _MAX_TOTAL_SOURCE_BYTES
    batch_size: int = _MAX_BATCH_ITEMS

    def __post_init__(self) -> None:
        for name in ("max_files", "max_file_bytes", "max_total_bytes"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value <= 0
            ):
                raise PdfCorpusError(f"{name} must be a positive integer")
        for name, maximum in (
            ("max_files", _MAX_PLAN_FILES),
            ("max_file_bytes", _MAX_SOURCE_BYTES),
            ("max_total_bytes", _MAX_TOTAL_SOURCE_BYTES),
        ):
            if getattr(self, name) > maximum:
                raise PdfCorpusError(f"{name} exceeds the supported limit")
        if self.max_file_bytes > self.max_total_bytes:
            raise PdfCorpusError("max_file_bytes cannot exceed max_total_bytes")
        if (
            isinstance(self.batch_size, bool)
            or not isinstance(self.batch_size, int)
            or not 1 <= self.batch_size <= _MAX_BATCH_ITEMS
        ):
            raise PdfCorpusError(
                f"batch_size must be between 1 and {_MAX_BATCH_ITEMS}"
            )


@dataclass(frozen=True)
class PreparedPdfCorpus:
    plans: tuple[PdfBatchPlan, ...]
    discovered_file_count: int
    duplicate_file_count: int
    unique_file_count: int
    total_source_bytes: int


@dataclass(frozen=True)
class ValidatedPdfExtraction:
    result: ExtractionResult
    transcript: PdfExtractionTranscript
    empty_page_count: int
    low_text_page_count: int
    native_text_utf8_bytes: int


@dataclass(frozen=True)
class PdfCorpusValidationSummary:
    document_count: int
    page_count: int
    empty_page_count: int
    low_text_page_count: int
    documents_requiring_ocr: int
    native_text_utf8_bytes: int
    source_bytes: int


def prepare_pdf_corpus(
    source_root: Path,
    *,
    limits: PdfCorpusLimits | None = None,
) -> PreparedPdfCorpus:
    """Discover exact PDFs and return existing hash-locked batch plans."""
    actual_limits = limits or PdfCorpusLimits()
    root = _absolute(source_root)
    _require_real_directory(root, "source root")
    relative_paths = _discover_pdf_paths(root, actual_limits.max_files)

    total_bytes = 0
    unique: dict[str, PdfBatchItem] = {}
    for relative_path in relative_paths:
        content = _read_regular_file(
            root / Path(relative_path),
            maximum_bytes=actual_limits.max_file_bytes,
            label="source PDF",
        )
        total_bytes += len(content)
        if total_bytes > actual_limits.max_total_bytes:
            raise PdfCorpusError(
                "source aggregate byte count exceeds the bound"
            )
        if not content.startswith(b"%PDF-"):
            raise PdfCorpusError("source does not have a PDF header")
        digest = hashlib.sha256(content).hexdigest()
        if digest in unique:
            continue
        unique[digest] = PdfBatchItem(
            source_id=f"pdf:sha256:{digest}",
            pdf_path=relative_path,
            output_directory=PurePosixPath(digest),
            sha256=digest,
            byte_size=len(content),
            locator=relative_path.as_posix(),
        )

    items = tuple(unique.values())
    if not items:
        raise PdfCorpusError("source root contains no PDF files")
    plans = tuple(
        PdfBatchPlan(
            schema_version=1,
            items=items[offset : offset + actual_limits.batch_size],
        )
        for offset in range(0, len(items), actual_limits.batch_size)
    )
    return PreparedPdfCorpus(
        plans=plans,
        discovered_file_count=len(relative_paths),
        duplicate_file_count=len(relative_paths) - len(items),
        unique_file_count=len(items),
        total_source_bytes=total_bytes,
    )


def publish_pdf_corpus_plans(
    directory: Path,
    plans: tuple[PdfBatchPlan, ...],
    *,
    limits: PdfCorpusLimits | None = None,
) -> str:
    """Publish an exact plan directory once; return created or unchanged."""
    if not plans:
        raise PdfCorpusPublicationError("corpus plan set cannot be empty")
    if len(plans) > _MAX_PLAN_FILES:
        raise PdfCorpusPublicationError(
            "corpus plan set exceeds the file limit"
        )
    _require_unique_corpus_items(plans)
    _require_content_addressed_items(plans)
    _require_corpus_plan_bounds(plans, limits or PdfCorpusLimits())
    expected = {
        _plan_filename(index): plan.to_json().encode("utf-8")
        for index, plan in enumerate(plans, start=1)
    }
    if any(len(content) > _MAX_PLAN_BYTES for content in expected.values()):
        raise PdfCorpusPublicationError("corpus plan exceeds the size limit")

    target = _absolute(directory)
    if os.path.lexists(target):
        _verify_plan_directory(target, expected)
        return "unchanged"

    _create_private_directories(target.parent)
    _require_real_directory(target.parent, "plan parent")
    staging: Path | None = None
    try:
        staging = Path(
            tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent)
        )
        os.chmod(staging, 0o700)
        for name, content in expected.items():
            _write_new_bytes(staging / name, content)
        _fsync_directory(staging)
        _rename_directory_no_replace(staging, target)
        staging = None
        _fsync_directory(target.parent)
    except PdfCorpusPublicationError:
        raise
    except OSError as error:
        raise PdfCorpusPublicationError(
            "could not publish corpus plans"
        ) from error
    finally:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)
    return "created"


def load_pdf_corpus_plans(
    directory: Path,
    *,
    limits: PdfCorpusLimits | None = None,
) -> tuple[PdfBatchPlan, ...]:
    """Load one bounded, private, non-symlinked directory of batch plans."""
    actual_limits = limits or PdfCorpusLimits()
    root = _absolute(directory)
    _require_real_directory(root, "plan directory")
    _require_mode(root, 0o700, "plan directory")
    entry_names = _bounded_directory_names(
        root,
        maximum_entries=min(_MAX_PLAN_FILES, actual_limits.max_files),
        excess_message="corpus plan item count exceeds the bound",
    )
    if not entry_names:
        raise PdfCorpusError("plan directory has an unsupported file count")
    expected_names = tuple(
        _plan_filename(index) for index in range(1, len(entry_names) + 1)
    )
    if entry_names != expected_names:
        raise PdfCorpusError("plan directory inventory is not canonical")

    plans: list[PdfBatchPlan] = []
    item_count = 0
    total_source_bytes = 0
    for name in entry_names:
        path = root / name
        _require_mode(path, 0o600, "plan file")
        content = _read_regular_file(
            path,
            maximum_bytes=_MAX_PLAN_BYTES,
            label="plan file",
        )
        try:
            text = content.decode("utf-8", errors="strict")
            json.loads(text, object_pairs_hook=_unique_json_object)
            plan = PdfBatchPlan.from_json(text)
        except (UnicodeDecodeError, ValueError) as error:
            raise PdfCorpusError("corpus plan is malformed") from error
        item_count, total_source_bytes = _extend_corpus_plan_bounds(
            plan.items,
            limits=actual_limits,
            item_count=item_count,
            total_source_bytes=total_source_bytes,
        )
        plans.append(plan)
    loaded = tuple(plans)
    _require_unique_corpus_items(loaded)
    _require_content_addressed_items(loaded)
    return loaded


def validate_pdf_extraction(
    item: PdfBatchItem,
    *,
    source_root: Path,
    output_root: Path,
    configuration: PdfExtractionConfiguration | None = None,
    artifact_limits: PdfExtractionArtifactLimits | None = None,
    max_source_bytes: int = _MAX_SOURCE_BYTES,
) -> ValidatedPdfExtraction:
    """Validate one source and its complete canonical owner artifact set."""
    actual_configuration = configuration or PdfExtractionConfiguration()
    actual_artifact_limits = artifact_limits or PdfExtractionArtifactLimits()
    source_base = _absolute(source_root)
    output_base = _absolute(output_root)
    _require_real_directory(source_base, "source root")
    _require_real_directory(output_base, "output root")
    _require_mode(output_base, 0o700, "output root")

    source = source_base / Path(item.pdf_path)
    output = output_base / Path(item.output_directory)
    source_content = _read_regular_file(
        source,
        maximum_bytes=max_source_bytes,
        label="source PDF",
    )
    if not source_content.startswith(b"%PDF-"):
        raise PdfCorpusError("source does not have a PDF header")
    if (
        len(source_content) != item.byte_size
        or hashlib.sha256(source_content).hexdigest() != item.sha256
    ):
        raise PdfCorpusError("source identity differs from the batch plan")

    _require_real_directory(output, "extraction directory")
    _require_mode(output, 0o700, "extraction directory")
    extraction_path = output / "extraction.json"
    pages_directory = output / "pages"
    expected_extraction_names = ("extraction.json", "pages")
    actual_extraction_names = _bounded_directory_names(
        output,
        maximum_entries=len(expected_extraction_names),
        excess_message="extraction artifact inventory is not canonical",
    )
    _require_exact_inventory(
        actual_extraction_names,
        expected_extraction_names,
        "extraction artifact inventory is not canonical",
    )
    _require_mode(extraction_path, 0o600, "extraction artifact")
    extraction_bytes = _read_regular_file(
        extraction_path,
        maximum_bytes=actual_artifact_limits.max_raw_extraction_bytes,
        label="extraction artifact",
    )
    try:
        extraction_text = extraction_bytes.decode("utf-8", errors="strict")
        result = deserialize_extraction_result(extraction_text)
        bundle = build_pdf_extraction_artifacts(
            result,
            configuration=actual_configuration,
            artifact_limits=actual_artifact_limits,
        )
    except (UnicodeDecodeError, TypeError, ValueError) as error:
        raise PdfCorpusError("extraction artifact is invalid") from error

    source_evidence = result.document.source
    expected_locator = item.locator or item.pdf_path.as_posix()
    if (
        source_evidence.source_id != item.source_id
        or source_evidence.content_hash != item.sha256
        or source_evidence.byte_length != item.byte_size
        or source_evidence.locator != expected_locator
    ):
        raise PdfCorpusError("extraction lineage differs from the batch plan")

    canonical = bundle.artifacts
    if canonical[0].relative_path != RAW_EXTRACTION_RELATIVE_PATH:
        raise PdfCorpusError("owner extraction artifact order is invalid")
    if extraction_bytes != canonical[0].content:
        raise PdfCorpusError("extraction artifact is not canonical")
    _require_real_directory(pages_directory, "page artifact directory")
    _require_mode(pages_directory, 0o700, "page artifact directory")
    expected_page_names = tuple(
        Path(value.relative_path).name for value in canonical[1:]
    )
    actual_page_names = _bounded_directory_names(
        pages_directory,
        maximum_entries=len(expected_page_names),
        excess_message="page artifact inventory is not canonical",
    )
    _require_exact_inventory(
        actual_page_names,
        expected_page_names,
        "page artifact inventory is not canonical",
    )

    replay_artifacts: list[PdfExtractionArtifactPayload] = [canonical[0]]
    for expected in canonical[1:]:
        page_path = pages_directory / Path(expected.relative_path).name
        _require_mode(page_path, 0o600, "page artifact")
        content = _read_regular_file(
            page_path,
            maximum_bytes=actual_artifact_limits.max_page_text_bytes,
            label="page artifact",
        )
        if content != expected.content:
            raise PdfCorpusError("page artifact differs from owner evidence")
        replay_artifacts.append(
            PdfExtractionArtifactPayload.create(
                relative_path=expected.relative_path,
                media_type=RAW_PAGE_TEXT_MEDIA_TYPE,
                content=content,
            )
        )
    replay_artifacts[0] = PdfExtractionArtifactPayload.create(
        relative_path=RAW_EXTRACTION_RELATIVE_PATH,
        media_type=RAW_EXTRACTION_MEDIA_TYPE,
        content=extraction_bytes,
    )
    transcript = read_pdf_extraction_transcript(
        tuple(replay_artifacts),
        expected_bundle_id=bundle.bundle_id,
        expected_source_sha256=item.sha256,
        expected_source_byte_size=item.byte_size,
        configuration=actual_configuration,
        artifact_limits=actual_artifact_limits,
    )
    empty_pages = sum(not page.text.strip() for page in transcript.pages)
    low_text_page_indices = {
        span.page_index
        for warning in result.warnings
        if warning.code == "pdf.low_text_density"
        for span in warning.source_spans
        if span.page_index is not None
    }
    return ValidatedPdfExtraction(
        result=result,
        transcript=transcript,
        empty_page_count=empty_pages,
        low_text_page_count=len(low_text_page_indices),
        native_text_utf8_bytes=sum(
            len(page.text.encode("utf-8")) for page in transcript.pages
        ),
    )


def validate_pdf_corpus(
    plans: tuple[PdfBatchPlan, ...],
    *,
    source_root: Path,
    output_root: Path,
    configuration: PdfExtractionConfiguration | None = None,
    artifact_limits: PdfExtractionArtifactLimits | None = None,
    limits: PdfCorpusLimits | None = None,
) -> PdfCorpusValidationSummary:
    """Validate a complete planned native-text extraction corpus."""
    actual_limits = limits or PdfCorpusLimits()
    _require_unique_corpus_items(plans)
    _require_content_addressed_items(plans)
    _require_corpus_plan_bounds(plans, actual_limits)
    output_base = _absolute(output_root)
    _require_real_directory(output_base, "output root")
    _require_mode(output_base, 0o700, "output root")
    expected_output_names = tuple(
        sorted(
            item.output_directory.as_posix()
            for plan in plans
            for item in plan.items
        )
    )
    actual_output_names = _bounded_directory_names(
        output_base,
        maximum_entries=len(expected_output_names),
        excess_message="corpus output inventory is not canonical",
    )
    _require_exact_inventory(
        actual_output_names,
        expected_output_names,
        "corpus output inventory is not canonical",
    )
    documents = pages = empty_pages = low_text_pages = 0
    documents_requiring_ocr = native_text_bytes = source_bytes = 0
    for plan in plans:
        for item in plan.items:
            validated = validate_pdf_extraction(
                item,
                source_root=source_root,
                output_root=output_root,
                configuration=configuration,
                artifact_limits=artifact_limits,
                max_source_bytes=actual_limits.max_file_bytes,
            )
            documents += 1
            page_count = len(validated.transcript.pages)
            pages += page_count
            empty_pages += validated.empty_page_count
            low_text_pages += validated.low_text_page_count
            documents_requiring_ocr += validated.empty_page_count > 0
            native_text_bytes += validated.native_text_utf8_bytes
            source_bytes += item.byte_size
    return PdfCorpusValidationSummary(
        document_count=documents,
        page_count=pages,
        empty_page_count=empty_pages,
        low_text_page_count=low_text_pages,
        documents_requiring_ocr=documents_requiring_ocr,
        native_text_utf8_bytes=native_text_bytes,
        source_bytes=source_bytes,
    )


def _discover_pdf_paths(
    root: Path, maximum_files: int
) -> tuple[PurePosixPath, ...]:
    discovered: list[PurePosixPath] = []

    def fail_closed(error: OSError) -> None:
        raise PdfCorpusError("source discovery failed") from error

    try:
        for base, directory_names, file_names in os.walk(
            root,
            followlinks=False,
            onerror=fail_closed,
        ):
            directory_names.sort()
            file_names.sort()
            for name in directory_names:
                if (Path(base) / name).is_symlink():
                    raise PdfCorpusError(
                        "source discovery encountered a symlinked directory"
                    )
            for name in file_names:
                if not name.lower().endswith(".pdf"):
                    continue
                path = Path(base) / name
                relative = PurePosixPath(path.relative_to(root).as_posix())
                discovered.append(relative)
                if len(discovered) > maximum_files:
                    raise PdfCorpusError("source file count exceeds the bound")
    except OSError as error:
        raise PdfCorpusError("source discovery failed") from error
    return tuple(sorted(discovered, key=PurePosixPath.as_posix))


def _read_regular_file(
    path: Path,
    *,
    maximum_bytes: int,
    label: str,
) -> bytes:
    try:
        if path.resolve() != path:
            raise PdfCorpusError(f"{label} cannot traverse a symlink")
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode):
            raise PdfCorpusError(f"{label} is not a safe regular file")
        if before.st_size <= 0 or before.st_size > maximum_bytes:
            raise PdfCorpusError(f"{label} size is outside the bounded range")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            opened = os.fstat(descriptor)
            identity = (opened.st_dev, opened.st_ino, opened.st_size)
            if identity != (before.st_dev, before.st_ino, before.st_size):
                raise PdfCorpusError(f"{label} changed before read")
            chunks: list[bytes] = []
            remaining = opened.st_size
            while remaining:
                chunk = os.read(descriptor, min(8 * 1024 * 1024, remaining))
                if not chunk:
                    raise PdfCorpusError(f"{label} ended during read")
                chunks.append(chunk)
                remaining -= len(chunk)
            if os.read(descriptor, 1):
                raise PdfCorpusError(f"{label} grew during read")
            after = os.fstat(descriptor)
            if (after.st_dev, after.st_ino, after.st_size) != identity:
                raise PdfCorpusError(f"{label} changed during read")
            return b"".join(chunks)
        finally:
            os.close(descriptor)
    except PdfCorpusError:
        raise
    except OSError as error:
        raise PdfCorpusError(f"could not safely read {label}") from error


def _require_unique_corpus_items(plans: tuple[PdfBatchPlan, ...]) -> None:
    if not plans:
        raise PdfCorpusError("corpus plan set cannot be empty")
    items = tuple(item for plan in plans for item in plan.items)
    for name, values in (
        ("source_id", tuple(item.source_id for item in items)),
        ("pdf_path", tuple(item.pdf_path.as_posix() for item in items)),
        (
            "output_directory",
            tuple(item.output_directory.as_posix() for item in items),
        ),
    ):
        if len(values) != len(set(values)):
            raise PdfCorpusError(
                f"corpus plans contain duplicate {name} values"
            )


def _require_corpus_plan_bounds(
    plans: tuple[PdfBatchPlan, ...],
    limits: PdfCorpusLimits,
) -> None:
    items = tuple(item for plan in plans for item in plan.items)
    _extend_corpus_plan_bounds(
        items,
        limits=limits,
        item_count=0,
        total_source_bytes=0,
    )


def _extend_corpus_plan_bounds(
    items: tuple[PdfBatchItem, ...],
    *,
    limits: PdfCorpusLimits,
    item_count: int,
    total_source_bytes: int,
) -> tuple[int, int]:
    item_count += len(items)
    if item_count > limits.max_files:
        raise PdfCorpusError("corpus plan item count exceeds the bound")
    for item in items:
        if item.byte_size > limits.max_file_bytes:
            raise PdfCorpusError("planned source size exceeds the bound")
        total_source_bytes += item.byte_size
        if total_source_bytes > limits.max_total_bytes:
            raise PdfCorpusError(
                "planned source aggregate byte count exceeds the bound"
            )
    return item_count, total_source_bytes


def _require_content_addressed_items(
    plans: tuple[PdfBatchPlan, ...],
) -> None:
    for plan in plans:
        for item in plan.items:
            if (
                item.source_id != f"pdf:sha256:{item.sha256}"
                or item.output_directory.as_posix() != item.sha256
            ):
                raise PdfCorpusError(
                    "corpus plan item is not content-addressed"
                )


def _unique_json_object(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, member in pairs:
        if key in value:
            raise ValueError("JSON contains a duplicate member")
        value[key] = member
    return value


def _bounded_directory_names(
    directory: Path,
    *,
    maximum_entries: int,
    excess_message: str,
) -> tuple[str, ...]:
    if maximum_entries < 0:
        raise AssertionError("directory inventory limit cannot be negative")
    names: list[str] = []
    try:
        with os.scandir(directory) as entries:
            for entry in entries:
                if len(names) >= maximum_entries:
                    raise PdfCorpusError(excess_message)
                names.append(entry.name)
    except PdfCorpusError:
        raise
    except OSError as error:
        raise PdfCorpusError("could not inspect directory inventory") from error
    return tuple(sorted(names))


def _require_exact_inventory(
    actual: tuple[str, ...],
    expected: tuple[str, ...],
    message: str,
) -> None:
    if len(actual) != len(expected) or set(actual) != set(expected):
        raise PdfCorpusError(message)


def _verify_plan_directory(target: Path, expected: dict[str, bytes]) -> None:
    _require_real_directory(target, "plan directory")
    _require_mode(target, 0o700, "plan directory")
    try:
        actual_names = _bounded_directory_names(
            target,
            maximum_entries=len(expected),
            excess_message="existing corpus plan inventory differs",
        )
        _require_exact_inventory(
            actual_names,
            tuple(expected),
            "existing corpus plan inventory differs",
        )
    except PdfCorpusError as error:
        raise PdfCorpusPublicationError(
            "existing corpus plan inventory differs"
        ) from error
    for name, content in expected.items():
        path = target / name
        _require_mode(path, 0o600, "plan file")
        actual = _read_regular_file(
            path,
            maximum_bytes=_MAX_PLAN_BYTES,
            label="plan file",
        )
        if actual != content:
            raise PdfCorpusPublicationError("existing corpus plan differs")


def _rename_directory_no_replace(source: Path, target: Path) -> None:
    library = ctypes.CDLL(None, use_errno=True)
    source_bytes = os.fsencode(source)
    target_bytes = os.fsencode(target)
    status: int
    if sys.platform == "darwin":
        rename_exclusive = library.renamex_np
        rename_exclusive.argtypes = [
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename_exclusive.restype = ctypes.c_int
        status = int(rename_exclusive(source_bytes, target_bytes, 0x00000004))
    elif sys.platform.startswith("linux"):
        try:
            rename_exclusive = library.renameat2
        except AttributeError as error:
            raise PdfCorpusPublicationError(
                "no-replace directory publication is unavailable"
            ) from error
        rename_exclusive.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename_exclusive.restype = ctypes.c_int
        status = int(
            rename_exclusive(
                -100,
                source_bytes,
                -100,
                target_bytes,
                0x00000001,
            )
        )
    else:
        raise PdfCorpusPublicationError(
            "no-replace directory publication is unavailable"
        )
    if status == 0:
        return
    error_number = ctypes.get_errno()
    if error_number in (errno.EEXIST, errno.ENOTEMPTY):
        raise PdfCorpusPublicationError(
            "corpus plan destination appeared during publication"
        )
    raise OSError(error_number, os.strerror(error_number))


def _plan_filename(index: int) -> str:
    if index <= 0 or index > _MAX_PLAN_FILES:
        raise PdfCorpusError("plan index exceeds the supported limit")
    name = f"batch-{index:05d}.json"
    if _PLAN_NAME.fullmatch(name) is None:
        raise AssertionError("internal plan filename is invalid")
    return name


def _absolute(path: Path) -> Path:
    return path.expanduser().absolute()


def _require_real_directory(path: Path, label: str) -> None:
    try:
        metadata = path.lstat()
        if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
            raise PdfCorpusError(f"{label} must be a non-symlink directory")
        if path.resolve() != path:
            raise PdfCorpusError(f"{label} cannot traverse a symlink")
    except FileNotFoundError as error:
        raise PdfCorpusError(f"{label} does not exist") from error
    except OSError as error:
        raise PdfCorpusError(f"could not inspect {label}") from error


def _require_mode(path: Path, expected: int, label: str) -> None:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise PdfCorpusError(f"could not inspect {label}") from error
    if stat.S_IMODE(metadata.st_mode) != expected:
        raise PdfCorpusError(f"{label} does not have private permissions")


def _create_private_directories(path: Path) -> None:
    missing: list[Path] = []
    current = path
    while not current.exists():
        missing.append(current)
        if current == current.parent:
            break
        current = current.parent
    _require_real_directory(current, "existing plan parent")
    for directory in reversed(missing):
        try:
            directory.mkdir(mode=0o700)
        except FileExistsError as error:
            raise PdfCorpusPublicationError(
                "plan parent changed during creation"
            ) from error


def _write_new_bytes(path: Path, content: bytes) -> None:
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
