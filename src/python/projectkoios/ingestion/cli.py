from __future__ import annotations

import argparse
import hashlib
import os
import stat
from collections.abc import Sequence
from io import BytesIO
from pathlib import Path

from projectkoios.ingestion.cache import (
    ExtractionCacheError,
    FilesystemExtractionCache,
)
from projectkoios.ingestion.models import ExtractionResult
from projectkoios.ingestion.pdf import (
    DEFAULT_MAXIMUM_PDF_PAGES,
    RAW_EXTRACTION_RELATIVE_PATH,
    PdfExtractionConfiguration,
    PyMuPdfExtractor,
    build_pdf_extraction_artifacts,
    extract_pdf_bytes,
    prepare_pdf_bytes_extraction,
)

Artifact = tuple[Path, str]


class ArtifactPublicationError(RuntimeError):
    """Raised after a CLI artifact publication fails and is rolled back."""


class ExtractionCacheOperationError(RuntimeError):
    """Raised when the optional extraction cache cannot be used safely."""


class _ArtifactWriteError(RuntimeError):
    """Records an exclusively created file that did not finish writing."""

    def __init__(self, path: Path, error: Exception) -> None:
        super().__init__(f"could not finish writing {path}: {error}")
        self.path = path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="koios-ingest-pdf")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--raw-text-directory", type=Path)
    parser.add_argument("--cache-root", type=Path)
    parser.add_argument("--locator")
    parser.add_argument("--low-text-threshold", type=int, default=40)
    parser.add_argument(
        "--maximum-pages", type=int, default=DEFAULT_MAXIMUM_PDF_PAGES
    )
    return parser


def extract_pdf_evidence(
    pdf: Path,
    *,
    source_id: str,
    cache_root: Path | None = None,
    locator: str | None = None,
    low_text_threshold: int = 40,
    expected_source_sha256: str | None = None,
    expected_source_byte_size: int | None = None,
    maximum_pages: int = DEFAULT_MAXIMUM_PDF_PAGES,
) -> tuple[bytes, ExtractionResult]:
    """Return exact PDF bytes and raw extraction, optionally from cache."""
    payload = _read_pdf_bytes(pdf)
    actual_sha256 = hashlib.sha256(payload).hexdigest()
    planned_sha256 = expected_source_sha256 or actual_sha256
    planned_size = (
        len(payload)
        if expected_source_byte_size is None
        else expected_source_byte_size
    )
    actual_locator = locator or pdf.name
    result: ExtractionResult
    if cache_root is None:
        result = extract_pdf_bytes(
            payload,
            source_id=source_id,
            locator=actual_locator,
            low_text_character_threshold=low_text_threshold,
            expected_source_sha256=planned_sha256,
            expected_source_byte_size=planned_size,
            maximum_pages=maximum_pages,
        )
    else:
        source, configuration = prepare_pdf_bytes_extraction(
            payload,
            source_id=source_id,
            locator=actual_locator,
            low_text_character_threshold=low_text_threshold,
            expected_source_sha256=planned_sha256,
            expected_source_byte_size=planned_size,
            maximum_pages=maximum_pages,
        )
        extractor = PyMuPdfExtractor(
            low_text_character_threshold=(
                configuration.low_text_character_threshold
            ),
            maximum_pages=configuration.maximum_pages,
        )
        cache = FilesystemExtractionCache(cache_root)
        cache_key = extractor.cache_key(source)
        try:
            cached_result = cache.get(cache_key)
            if cached_result is None:
                result = extractor.extract(source, content=BytesIO(payload))
                cache.put(cache_key, result)
            else:
                result = cached_result
        except (ExtractionCacheError, OSError, ValueError) as error:
            raise ExtractionCacheOperationError(str(error)) from error
    return payload, result


def ingest_pdf_artifacts(
    pdf: Path,
    *,
    source_id: str,
    output: Path,
    raw_text_directory: Path | None = None,
    cache_root: Path | None = None,
    locator: str | None = None,
    low_text_threshold: int = 40,
    expected_source_sha256: str | None = None,
    expected_source_byte_size: int | None = None,
    maximum_pages: int = DEFAULT_MAXIMUM_PDF_PAGES,
) -> ExtractionResult:
    """Extract one PDF and exclusively publish its raw evidence artifacts."""
    _, result = extract_pdf_evidence(
        pdf,
        source_id=source_id,
        cache_root=cache_root,
        locator=locator,
        low_text_threshold=low_text_threshold,
        expected_source_sha256=expected_source_sha256,
        expected_source_byte_size=expected_source_byte_size,
        maximum_pages=maximum_pages,
    )
    configuration = PdfExtractionConfiguration(
        low_text_character_threshold=low_text_threshold,
        maximum_pages=maximum_pages,
    )
    bundle = build_pdf_extraction_artifacts(
        result,
        configuration=configuration,
    )
    extraction_artifact = bundle.artifacts[0]
    if extraction_artifact.relative_path != RAW_EXTRACTION_RELATIVE_PATH:
        raise RuntimeError("owner extraction artifact order is invalid")
    artifacts: list[Artifact] = []
    if raw_text_directory is not None:
        artifacts.extend(
            (
                raw_text_directory / Path(item.relative_path).name,
                item.content.decode("utf-8", errors="strict"),
            )
            for item in bundle.artifacts[1:]
        )
    artifacts.append(
        (
            output,
            extraction_artifact.content.decode("utf-8", errors="strict"),
        )
    )
    _publish_artifacts(artifacts)
    return result


def main(arguments: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(arguments)
    try:
        ingest_pdf_artifacts(
            args.pdf,
            source_id=args.source_id,
            output=args.output,
            raw_text_directory=args.raw_text_directory,
            cache_root=args.cache_root,
            locator=args.locator,
            low_text_threshold=args.low_text_threshold,
            maximum_pages=args.maximum_pages,
        )
    except ExtractionCacheOperationError as error:
        parser.error(f"extraction cache failure: {error}")
    except (OSError, ValueError) as error:
        parser.error(f"PDF ingestion failure: {error}")
    except ArtifactPublicationError as error:
        parser.error(str(error))
    print(args.output)
    return 0


def _read_pdf_bytes(path: Path) -> bytes:
    """Read one regular PDF without following symbolic links."""
    source = path.expanduser().absolute()
    try:
        if source.resolve() != source:
            raise ValueError("PDF source cannot traverse a symlink")
        before = source.lstat()
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("PDF source must be a safe regular file")
        descriptor = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            opened = os.fstat(descriptor)
            identity = (opened.st_dev, opened.st_ino, opened.st_size)
            if identity != (before.st_dev, before.st_ino, before.st_size):
                raise ValueError("PDF source changed before read")
            chunks: list[bytes] = []
            remaining = opened.st_size
            while remaining:
                chunk = os.read(descriptor, min(8 * 1024 * 1024, remaining))
                if not chunk:
                    raise ValueError("PDF source ended during read")
                chunks.append(chunk)
                remaining -= len(chunk)
            if os.read(descriptor, 1):
                raise ValueError("PDF source grew during read")
            after = os.fstat(descriptor)
            if (after.st_dev, after.st_ino, after.st_size) != identity:
                raise ValueError("PDF source changed during read")
            return b"".join(chunks)
        finally:
            os.close(descriptor)
    except (OSError, RuntimeError) as error:
        raise ValueError("could not safely read PDF source") from error


def _publish_artifacts(artifacts: Sequence[Artifact]) -> None:
    normalized_paths = tuple(path.absolute() for path, _ in artifacts)
    if len(set(normalized_paths)) != len(normalized_paths):
        raise ArtifactPublicationError(
            "refusing to publish duplicate extraction artifact paths"
        )
    for path in normalized_paths:
        if os.path.lexists(path):
            raise ArtifactPublicationError(
                f"refusing to overwrite extraction artifact: {path}"
            )

    created_files: list[Path] = []
    created_directories: list[Path] = []
    try:
        for path, text in artifacts:
            _create_parent_directories(path.parent, created_directories)
            _write_new(path, text)
            created_files.append(path)
    except Exception as error:
        if isinstance(error, _ArtifactWriteError):
            created_files.append(error.path)
        rollback_failures = _rollback(created_files, created_directories)
        message = f"failed to publish extraction artifacts: {error}"
        if rollback_failures:
            message += "; rollback incomplete: " + ", ".join(
                str(path) for path in rollback_failures
            )
        else:
            message += "; rolled back artifacts created by this invocation"
        raise ArtifactPublicationError(message) from error


def _create_parent_directories(
    parent: Path,
    created_directories: list[Path],
) -> None:
    missing: list[Path] = []
    current = parent
    while not current.exists():
        missing.append(current)
        if current == current.parent:
            break
        current = current.parent
    for directory in reversed(missing):
        try:
            directory.mkdir(mode=0o700)
        except FileExistsError:
            if not directory.is_dir():
                raise
        else:
            created_directories.append(directory)


def _write_new(path: Path, text: str) -> None:
    created = False
    descriptor: int | None = None
    try:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        created = True
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            descriptor = None
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception as error:
        if descriptor is not None:
            os.close(descriptor)
        if created:
            raise _ArtifactWriteError(path, error) from error
        raise


def _rollback(
    files: Sequence[Path],
    directories: Sequence[Path],
) -> tuple[Path, ...]:
    failures: list[Path] = []
    for path in reversed(files):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            failures.append(path)
    for path in reversed(directories):
        try:
            path.rmdir()
        except OSError:
            if path.exists():
                failures.append(path)
    return tuple(failures)


if __name__ == "__main__":  # pragma: no cover - exercised by smoke tests
    raise SystemExit(main())
