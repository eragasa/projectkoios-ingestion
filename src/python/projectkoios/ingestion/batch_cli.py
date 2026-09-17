from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from projectkoios.ingestion.batch import PdfBatchItem, PdfBatchPlan
from projectkoios.ingestion.cli import (
    ArtifactPublicationError,
    ExtractionCacheOperationError,
    ingest_pdf_artifacts,
)
from projectkoios.ingestion.models import ExtractionResult


@dataclass(frozen=True)
class _ResolvedItem:
    item: PdfBatchItem
    pdf: Path
    output_directory: Path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="koios-ingest-pdf-batch")
    parser.add_argument("plan", type=Path)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--cache-root", type=Path)
    parser.add_argument("--low-text-threshold", type=int, default=40)
    parser.add_argument("--apply", action="store_true")
    return parser


def _resolve_items(
    plan: PdfBatchPlan,
    *,
    source_root: Path,
    output_root: Path,
) -> tuple[_ResolvedItem, ...]:
    source_root = source_root.expanduser().resolve()
    output_root = output_root.expanduser().resolve()
    if not source_root.is_dir():
        raise ValueError("source root must be an existing directory")
    resolved: list[_ResolvedItem] = []
    for item in plan.items:
        pdf = (source_root / Path(item.pdf_path)).resolve()
        if not pdf.is_relative_to(source_root):
            raise ValueError(f"source PDF escapes source root: {item.pdf_path}")
        if not pdf.is_file():
            raise ValueError(
                f"source PDF is not a regular file: {item.pdf_path}"
            )
        content = pdf.read_bytes()
        if not content.startswith(b"%PDF-"):
            raise ValueError(
                f"source does not have a PDF header: {item.pdf_path}"
            )
        if len(content) != item.byte_size:
            raise ValueError(f"source size changed: {item.pdf_path}")
        if hashlib.sha256(content).hexdigest() != item.sha256:
            raise ValueError(f"source hash changed: {item.pdf_path}")
        raw_output_directory = output_root / Path(item.output_directory)
        if os.path.lexists(raw_output_directory):
            raise FileExistsError(
                "refusing to overwrite batch output directory: "
                f"{raw_output_directory}"
            )
        output_directory = raw_output_directory.resolve()
        if not output_directory.is_relative_to(output_root):
            raise ValueError(
                f"output directory escapes output root: {item.output_directory}"
            )
        resolved.append(_ResolvedItem(item, pdf, output_directory))
    return tuple(resolved)


def _planned_summary(items: tuple[_ResolvedItem, ...]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "status": "planned",
        "items": [
            {
                "source_id": resolved.item.source_id,
                "pdf_path": resolved.item.pdf_path.as_posix(),
                "output_directory": resolved.item.output_directory.as_posix(),
                "sha256": resolved.item.sha256,
                "byte_size": resolved.item.byte_size,
            }
            for resolved in items
        ],
    }


def _completed_item(
    resolved: _ResolvedItem,
    result: ExtractionResult,
) -> dict[str, object]:
    pages = result.document.pages
    blocks = tuple(block for page in pages for block in page.blocks)
    output = resolved.output_directory / "extraction.json"
    return {
        "source_id": resolved.item.source_id,
        "pdf_path": resolved.item.pdf_path.as_posix(),
        "output_directory": resolved.item.output_directory.as_posix(),
        "extraction_artifact": (
            resolved.item.output_directory / "extraction.json"
        ).as_posix(),
        "raw_text_directory": (
            resolved.item.output_directory / "pages"
        ).as_posix(),
        "source_content_hash": result.manifest.source_content_hash,
        "document_id": result.document.document_id,
        "manifest_id": result.manifest.manifest_id,
        "contract_version": result.manifest.contract_version,
        "extractor_name": result.manifest.extractor_name,
        "extractor_version": result.manifest.extractor_version,
        "page_count": len(pages),
        "block_count": len(blocks),
        "native_text_character_count": sum(
            len(block.text or "") for block in blocks
        ),
        "image_block_count": sum(block.kind == "image" for block in blocks),
        "minimum_page_quality": min(
            (page.extraction_quality for page in pages), default=None
        ),
        "warning_count": len(result.warnings),
        "extraction_artifact_sha256": hashlib.sha256(
            output.read_bytes()
        ).hexdigest(),
    }


def main(arguments: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(arguments)
    try:
        plan = PdfBatchPlan.from_json(args.plan.read_text(encoding="utf-8"))
        resolved = _resolve_items(
            plan,
            source_root=args.source_root,
            output_root=args.output_root,
        )
    except (OSError, ValueError) as error:
        parser.error(f"invalid PDF batch plan: {error}")
    if not args.apply:
        print(json.dumps(_planned_summary(resolved), indent=2))
        return 2

    completed: list[dict[str, object]] = []
    output_root = args.output_root.expanduser().resolve()
    try:
        for item in resolved:
            current_output = (
                item.output_directory.parent.resolve()
                / item.output_directory.name
            )
            if (
                not current_output.is_relative_to(output_root)
                or current_output != item.output_directory
            ):
                raise ValueError("batch output path changed after planning")
            result = ingest_pdf_artifacts(
                item.pdf,
                source_id=item.item.source_id,
                output=item.output_directory / "extraction.json",
                raw_text_directory=item.output_directory / "pages",
                cache_root=args.cache_root,
                locator=item.item.locator or item.item.pdf_path.as_posix(),
                low_text_threshold=args.low_text_threshold,
                expected_source_sha256=item.item.sha256,
                expected_source_byte_size=item.item.byte_size,
            )
            completed.append(_completed_item(item, result))
    except (
        ArtifactPublicationError,
        ExtractionCacheOperationError,
        OSError,
        ValueError,
    ) as error:
        parser.error(
            f"batch stopped after {len(completed)} completed items: {error}"
        )
    print(
        json.dumps(
            {
                "schema_version": 1,
                "status": "completed",
                "items": completed,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
