from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from io import BytesIO
from pathlib import Path

from projectkoios.ingestion.cache import (
    ExtractionCacheError,
    FilesystemExtractionCache,
)
from projectkoios.ingestion.models import ExtractionResult, SourceDocument
from projectkoios.ingestion.pdf import PyMuPdfExtractor
from projectkoios.ingestion.serialization import serialize_contract

Artifact = tuple[Path, str]


class ArtifactPublicationError(RuntimeError):
    """Raised after a CLI artifact publication fails and is rolled back."""


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
    return parser


def main(arguments: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(arguments)
    payload = args.pdf.read_bytes()
    source = SourceDocument.from_bytes(
        payload,
        source_id=args.source_id,
        media_type="application/pdf",
        locator=args.locator or args.pdf.name,
    )
    extractor = PyMuPdfExtractor(
        low_text_character_threshold=args.low_text_threshold
    )
    result: ExtractionResult
    if args.cache_root is None:
        result = extractor.extract(source, content=BytesIO(payload))
    else:
        cache = FilesystemExtractionCache(args.cache_root)
        cache_key = extractor.cache_key(source)
        try:
            cached_result = cache.get(cache_key)
        except (ExtractionCacheError, OSError) as error:
            parser.error(f"extraction cache failure: {error}")
        if cached_result is None:
            result = extractor.extract(source, content=BytesIO(payload))
            try:
                cache.put(cache_key, result)
            except (ExtractionCacheError, OSError, ValueError) as error:
                parser.error(f"extraction cache failure: {error}")
        else:
            result = cached_result
    artifacts = _raw_page_artifacts(args.raw_text_directory, result)
    artifacts.append((args.output, serialize_contract(result) + "\n"))
    try:
        _publish_artifacts(artifacts)
    except ArtifactPublicationError as error:
        parser.error(str(error))
    print(args.output)
    return 0


def _raw_page_artifacts(
    directory: Path | None,
    result: ExtractionResult,
) -> list[Artifact]:
    if directory is None:
        return []
    artifacts: list[Artifact] = []
    for page in result.document.pages:
        label = page.printed_page_label or "unknown"
        blocks = tuple(
            block.text
            for block in page.blocks
            if block.kind == "text" and block.text is not None
        )
        text = (
            f"<!-- pdf-page: {page.page_index + 1}; "
            f"printed-page: {label} -->\n\n"
            + "\n\n".join(blocks)
            + "\n"
        )
        artifacts.append(
            (directory / f"page-{page.page_index + 1:04d}.txt", text)
        )
    return artifacts


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
            directory.mkdir()
        except FileExistsError:
            if not directory.is_dir():
                raise
        else:
            created_directories.append(directory)


def _write_new(path: Path, text: str) -> None:
    created = False
    try:
        with path.open("x", encoding="utf-8") as stream:
            created = True
            stream.write(text)
    except Exception as error:
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
