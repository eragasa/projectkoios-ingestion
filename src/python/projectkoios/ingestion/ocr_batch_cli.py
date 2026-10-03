"""Dry-run-first selective local-Tesseract OCR composition command."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from projectkoios.ingestion.cache import _require_bounded_json_nesting
from projectkoios.ingestion.cli import (
    ArtifactPublicationError,
    ExtractionCacheOperationError,
    _publish_artifacts,
    extract_pdf_evidence,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.ocr.batch.item import SelectiveOCRItem
from projectkoios.ingestion.ocr.batch.page import SelectiveOCRPage
from projectkoios.ingestion.ocr.batch.plan import SelectiveOCRPlan
from projectkoios.ingestion.ocr.batch.publication import (
    SelectiveOCRPublication,
)
from projectkoios.ingestion.ocr.contracts import (
    OCRConfiguration,
    OCROutputMode,
    OCRPageImage,
    OCRProcessorIdentity,
    OCRRequest,
    OCRResult,
    OCRSelection,
    build_ocr_cache_key,
)
from projectkoios.ingestion.pdf.adapters.pymupdf.rendering import (
    PyMuPdfRegionRenderer,
)
from projectkoios.ingestion.pdf.models import PageRegionSelection
from projectkoios.ingestion.serialization import (
    contract_dict,
    serialize_contract,
)
from projectkoios.ingestion.storage.artifact import ArtifactPublicationItem
from projectkoios.ingestion.tesseract import (
    TesseractAdapterConfiguration,
    TesseractLanguageBinding,
    TesseractOCRProcessor,
)

_MAX_PLAN_BYTES = 16_000_000
_MAX_EXTRACTION_BYTES = 128_000_000
_MAX_RESULT_ARTIFACT_BYTES = 256_000_000


@dataclass(frozen=True, slots=True)
class _ResolvedOCRPage:
    selection: SelectiveOCRPage
    artifact: Path
    existing: bool


@dataclass(frozen=True, slots=True)
class _ResolvedOCRItem:
    contract: SelectiveOCRItem
    pdf: Path
    ingestion_directory: Path
    extraction_artifact: Path
    extraction_value: dict[str, object]
    output_root: Path
    pages: tuple[_ResolvedOCRPage, ...]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="koios-run-selective-ocr")
    parser.add_argument("plan", type=Path)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--ingestion-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--cache-root", type=Path)
    parser.add_argument("--low-text-threshold", type=int, default=40)
    parser.add_argument("--tesseract-executable", type=Path, required=True)
    parser.add_argument("--traineddata", type=Path, required=True)
    parser.add_argument("--language", default="en")
    parser.add_argument("--resource-name", default="eng")
    parser.add_argument("--resolution-dpi", type=int, default=300)
    parser.add_argument("--timeout-milliseconds", type=int, default=30_000)
    parser.add_argument("--page-segmentation-mode", type=int, default=6)
    parser.add_argument(
        "--output-mode",
        choices=tuple(mode.value for mode in OCROutputMode),
        default=OCROutputMode.TOKENS_AND_LINES.value,
    )
    parser.add_argument("--apply", action="store_true")
    return parser


def _read_bounded(path: Path, maximum: int, label: str) -> bytes:
    try:
        before = path.lstat()
    except OSError as error:
        raise ValueError(f"{label} is unavailable") from error
    if (
        not stat.S_ISREG(before.st_mode)
        or stat.S_ISLNK(before.st_mode)
        or before.st_size <= 0
        or before.st_size > maximum
    ):
        raise ValueError(f"{label} is not a bounded regular file")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
        ) != (before.st_dev, before.st_ino, before.st_size):
            raise ValueError(f"{label} changed during preflight")
        chunks: list[bytes] = []
        remaining = maximum + 1
        while remaining:
            chunk = os.read(descriptor, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        content = b"".join(chunks)
        after = os.fstat(descriptor)
        if len(content) != opened.st_size or (
            after.st_dev,
            after.st_ino,
            after.st_size,
        ) != (opened.st_dev, opened.st_ino, opened.st_size):
            raise ValueError(f"{label} changed during read")
        return content
    finally:
        os.close(descriptor)


def _safe_root(
    path: Path,
    label: str,
    *,
    require_private: bool = False,
) -> Path:
    expanded = path.expanduser().absolute()
    if expanded.is_symlink() or not expanded.is_dir():
        raise ValueError(f"{label} must be a non-symlink directory")
    resolved = expanded.resolve()
    if resolved != expanded:
        raise ValueError(f"{label} cannot traverse symlinks")
    if require_private and stat.S_IMODE(resolved.stat().st_mode) & 0o077:
        raise ValueError(f"{label} permissions must exclude group and others")
    return resolved


def _safe_existing_member(root: Path, relative: Path, label: str) -> Path:
    candidate = (root / relative).absolute()
    if candidate.is_symlink() or candidate.resolve() != candidate:
        raise ValueError(f"{label} cannot traverse symlinks")
    if not candidate.is_relative_to(root) or not candidate.is_file():
        raise ValueError(f"{label} must be a regular file within its root")
    return candidate


def _safe_tool_file(path: Path, label: str) -> Path:
    try:
        target = path.expanduser().resolve(strict=True)
        metadata = target.lstat()
    except OSError as error:
        raise ValueError(f"{label} is unavailable") from error
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise ValueError(f"{label} must resolve to a regular file")
    return target


def _safe_output_artifact(
    root: Path,
    relative_directory: Path,
    page_index: int,
) -> Path:
    page_directory = relative_directory / f"page-{page_index + 1:06d}"
    directory = (root / page_directory).absolute()
    if not directory.is_relative_to(root):
        raise ValueError("selective OCR output escapes its root")
    current = root
    for part in page_directory.parts:
        current = current / part
        if os.path.lexists(current):
            if current.is_symlink() or not current.is_dir():
                raise ValueError("selective OCR output path is unsafe")
            if stat.S_IMODE(current.stat().st_mode) & 0o077:
                raise ValueError(
                    "selective OCR output directories must be private"
                )
    artifact = directory / "result.json"
    if os.path.lexists(artifact) and (
        artifact.is_symlink() or not artifact.is_file()
    ):
        raise ValueError("selective OCR artifact is unsafe")
    return artifact


def _load_json(content: bytes, label: str) -> dict[str, object]:
    try:
        text = content.decode("utf-8", errors="strict")
        _require_bounded_json_nesting(text)
        value = json.loads(text)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        ValueError,
    ) as error:
        raise ValueError(f"{label} is invalid JSON") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _validate_extraction(
    *,
    item: SelectiveOCRItem,
    content: bytes,
) -> dict[str, object]:
    if hashlib.sha256(content).hexdigest() != item.extraction_sha256:
        raise ValueError("selective OCR extraction hash changed")
    value = _load_json(content, "selective OCR extraction")
    document = value.get("document")
    manifest = value.get("manifest")
    if not isinstance(document, dict) or not isinstance(manifest, dict):
        raise ValueError("selective OCR extraction has an invalid shape")
    source = document.get("source")
    pages = document.get("pages")
    if (
        not isinstance(source, dict)
        or not isinstance(pages, list)
        or source.get("source_id") != item.source.source_id
        or source.get("content_hash") != item.source.sha256
        or source.get("byte_length") != item.source.byte_size
        or manifest.get("source_id") != item.source.source_id
        or manifest.get("source_content_hash") != item.source.sha256
        or manifest.get("status") != "completed"
    ):
        raise ValueError("selective OCR extraction identity is inconsistent")
    if any(page.page_index >= len(pages) for page in item.pages):
        raise ValueError("selective OCR page index exceeds extraction pages")
    return value


def _resolve_plan(
    plan: SelectiveOCRPlan,
    *,
    source_root: Path,
    ingestion_root: Path,
    output_root: Path,
) -> tuple[_ResolvedOCRItem, ...]:
    resolved: list[_ResolvedOCRItem] = []
    for item in plan.items:
        pdf = _safe_existing_member(
            source_root,
            Path(item.source.pdf_path),
            "selective OCR source PDF",
        )
        pdf_content = _read_bounded(
            pdf,
            item.source.byte_size,
            "selective OCR source PDF",
        )
        if (
            len(pdf_content) != item.source.byte_size
            or hashlib.sha256(pdf_content).hexdigest() != item.source.sha256
            or not pdf_content.startswith(b"%PDF-")
        ):
            raise ValueError("selective OCR source PDF identity changed")
        ingestion_directory = (
            ingestion_root / Path(item.source.output_directory)
        ).absolute()
        if (
            not ingestion_directory.is_relative_to(ingestion_root)
            or ingestion_directory.is_symlink()
            or not ingestion_directory.is_dir()
            or ingestion_directory.resolve() != ingestion_directory
        ):
            raise ValueError("selective OCR ingestion directory is unsafe")
        extraction_artifact = _safe_existing_member(
            ingestion_directory,
            Path("extraction.json"),
            "selective OCR extraction artifact",
        )
        extraction_content = _read_bounded(
            extraction_artifact,
            _MAX_EXTRACTION_BYTES,
            "selective OCR extraction artifact",
        )
        extraction_value = _validate_extraction(
            item=item,
            content=extraction_content,
        )
        pages: list[_ResolvedOCRPage] = []
        for page in item.pages:
            artifact = _safe_output_artifact(
                output_root,
                Path(item.output_directory),
                page.page_index,
            )
            pages.append(
                _ResolvedOCRPage(
                    selection=page,
                    artifact=artifact,
                    existing=os.path.lexists(artifact),
                )
            )
        resolved.append(
            _ResolvedOCRItem(
                contract=item,
                pdf=pdf,
                ingestion_directory=ingestion_directory,
                extraction_artifact=extraction_artifact,
                extraction_value=extraction_value,
                output_root=output_root,
                pages=tuple(pages),
            )
        )
    return tuple(resolved)


def _native_text_block_ids(page: object) -> tuple[str, ...]:
    blocks = getattr(page, "blocks", None)
    if not isinstance(blocks, tuple):
        raise TypeError("extracted OCR page has invalid blocks")
    return tuple(
        block.block_id
        for block in blocks
        if isinstance(getattr(block, "text", None), str) and block.text
    )


def _request_for_page(
    *,
    item: _ResolvedOCRItem,
    page: _ResolvedOCRPage,
    payload: bytes,
    extraction: object,
    renderer: PyMuPdfRegionRenderer,
    configuration: OCRConfiguration,
) -> OCRRequest:
    document = getattr(extraction, "document", None)
    pages = getattr(document, "pages", None)
    source = getattr(document, "source", None)
    if not isinstance(pages, tuple) or source is None:
        raise TypeError("replayed OCR extraction has an invalid document")
    extracted_page = pages[page.selection.page_index]
    rendered = renderer.render(
        source,
        BytesIO(payload),
        (
            PageRegionSelection.for_full_page(
                source,
                page.selection.page_index,
            ),
        ),
    )
    if len(rendered) != 1:
        raise ValueError("selective OCR renderer returned invalid coverage")
    image = OCRPageImage.from_rendered_region(rendered[0])
    block_ids = _native_text_block_ids(extracted_page)
    selection = OCRSelection.create(
        image,
        native_text_page=extracted_page if block_ids else None,
        native_text_block_ids=block_ids,
    )
    return OCRRequest.create((selection,), configuration=configuration)


def _validate_existing_result(
    *,
    artifact: Path,
    item: SelectiveOCRItem,
    page: SelectiveOCRPage,
    request: OCRRequest,
    processor_identity: OCRProcessorIdentity,
) -> dict[str, object]:
    content = _read_bounded(
        artifact,
        _MAX_RESULT_ARTIFACT_BYTES,
        "selective OCR result artifact",
    )
    value = _load_json(content, "selective OCR result artifact")
    result = value.get("result")
    if not isinstance(result, dict):
        raise ValueError("existing selective OCR result is inconsistent")
    request_value = result.get("request")
    processor_value = result.get("processor_identity")
    results = result.get("selection_results")
    result_id = result.get("result_id")
    expected_publication_id = stable_id(
        "selective-ocr-publication",
        SelectiveOCRPublication.CONTRACT_VERSION,
        item.source.sha256,
        item.extraction_sha256,
        page.page_index,
        result_id,
    )
    if (
        value.get("publication_id") != expected_publication_id
        or value.get("source_sha256") != item.source.sha256
        or value.get("extraction_sha256") != item.extraction_sha256
        or value.get("page_index") != page.page_index
        or request_value != contract_dict(request)
        or processor_value != contract_dict(processor_identity)
        or result.get("cache_key")
        != build_ocr_cache_key(
            request=request,
            processor_identity=processor_identity,
        )
        or not isinstance(result_id, str)
        or not isinstance(result.get("status"), str)
        or not isinstance(results, list)
        or len(results) != 1
        or not isinstance(results[0], dict)
        or results[0].get("selection_id") != request.selections[0].selection_id
        or results[0].get("image_id") != request.selections[0].image.image_id
    ):
        raise ValueError("existing selective OCR result is inconsistent")
    return value


def _summary(
    *,
    item: _ResolvedOCRItem,
    page: _ResolvedOCRPage,
    action: str,
    value: dict[str, object],
) -> dict[str, object]:
    result = value.get("result")
    if not isinstance(result, dict):
        raise ValueError("selective OCR publication summary is invalid")
    results = result["selection_results"]
    if not isinstance(results, list) or not isinstance(results[0], dict):
        raise ValueError("selective OCR result summary is invalid")
    selection_result = results[0]
    tokens = selection_result.get("tokens")
    lines = selection_result.get("lines")
    warnings = selection_result.get("warnings")
    if (
        not isinstance(tokens, list)
        or not isinstance(lines, list)
        or not isinstance(warnings, list)
    ):
        raise ValueError("selective OCR result evidence is invalid")
    return {
        "source_id": item.contract.source.source_id,
        "page_index": page.selection.page_index,
        "action": action,
        "status": result["status"],
        "selection_status": selection_result.get("status"),
        "token_count": len(tokens),
        "line_count": len(lines),
        "warning_count": len(warnings),
        "publication_id": value["publication_id"],
        "result_id": result["result_id"],
        "artifact": (
            item.contract.output_directory
            / f"page-{page.selection.page_index + 1:06d}"
            / "result.json"
        ).as_posix(),
        "artifact_sha256": hashlib.sha256(
            page.artifact.read_bytes()
        ).hexdigest(),
        "native_text_preserved_separately": True,
    }


def main(arguments: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(arguments)
    try:
        plan_path = args.plan.expanduser().absolute()
        plan_content = _read_bounded(
            plan_path,
            _MAX_PLAN_BYTES,
            "selective OCR plan",
        )
        plan = SelectiveOCRPlan.from_json(
            plan_content.decode("utf-8", errors="strict")
        )
        source_root = _safe_root(args.source_root, "source root")
        ingestion_root = _safe_root(args.ingestion_root, "ingestion root")
        output_root = _safe_root(
            args.output_root,
            "output root",
            require_private=True,
        )
        executable = _safe_tool_file(
            args.tesseract_executable,
            "Tesseract executable",
        )
        if not os.access(executable, os.X_OK):
            raise ValueError("Tesseract executable is not executable")
        traineddata = _safe_tool_file(
            args.traineddata,
            "Tesseract traineddata",
        )
        resolved = _resolve_plan(
            plan,
            source_root=source_root,
            ingestion_root=ingestion_root,
            output_root=output_root,
        )
        ocr_configuration = OCRConfiguration(
            languages=(args.language,),
            output_mode=OCROutputMode(args.output_mode),
        )
        processor = TesseractOCRProcessor(
            executable=executable,
            language_bindings=(
                TesseractLanguageBinding(
                    language=args.language,
                    resource_name=args.resource_name,
                    traineddata_path=traineddata,
                ),
            ),
            configuration=TesseractAdapterConfiguration(
                timeout_milliseconds=args.timeout_milliseconds,
                page_segmentation_mode=args.page_segmentation_mode,
            ),
        )
        renderer = PyMuPdfRegionRenderer(resolution_dpi=args.resolution_dpi)
    except (OSError, TypeError, UnicodeDecodeError, ValueError) as error:
        parser.error(f"invalid selective OCR plan: {error}")

    if not args.apply:
        print(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "planned",
                    "ocr_execution": "not_executed",
                    "items": [
                        {
                            "source_id": item.contract.source.source_id,
                            "page_index": page.selection.page_index,
                            "action": (
                                "verify_existing" if page.existing else "create"
                            ),
                        }
                        for item in resolved
                        for page in item.pages
                    ],
                },
                indent=2,
            )
        )
        return 2

    completed: list[dict[str, object]] = []
    try:
        for item in resolved:
            payload, extraction = extract_pdf_evidence(
                item.pdf,
                source_id=item.contract.source.source_id,
                cache_root=args.cache_root,
                locator=(
                    item.contract.source.locator
                    or item.contract.source.pdf_path.as_posix()
                ),
                low_text_threshold=args.low_text_threshold,
                expected_source_sha256=item.contract.source.sha256,
                expected_source_byte_size=item.contract.source.byte_size,
            )
            current_extraction = _read_bounded(
                item.extraction_artifact,
                _MAX_EXTRACTION_BYTES,
                "selective OCR extraction artifact",
            )
            if hashlib.sha256(current_extraction).hexdigest() != (
                item.contract.extraction_sha256
            ):
                raise ValueError(
                    "selective OCR extraction changed after preflight"
                )
            if item.extraction_value.get("document") != contract_dict(
                extraction
            ).get("document"):
                raise ValueError("selective OCR extraction replay changed")
            for page in item.pages:
                current_artifact = _safe_output_artifact(
                    item.output_root,
                    Path(item.contract.output_directory),
                    page.selection.page_index,
                )
                if current_artifact != page.artifact:
                    raise ValueError(
                        "selective OCR output path changed after preflight"
                    )
                request = _request_for_page(
                    item=item,
                    page=page,
                    payload=payload,
                    extraction=extraction,
                    renderer=renderer,
                    configuration=ocr_configuration,
                )
                processor_identity = processor.identity_for(request)
                if page.existing:
                    value = _validate_existing_result(
                        artifact=page.artifact,
                        item=item.contract,
                        page=page.selection,
                        request=request,
                        processor_identity=processor_identity,
                    )
                    action = "unchanged"
                else:
                    result: OCRResult = processor.action(request=request)
                    publication = SelectiveOCRPublication.create(
                        item=item.contract,
                        page=page.selection,
                        result=result,
                    )
                    _publish_artifacts(
                        [
                            ArtifactPublicationItem(
                                path=page.artifact,
                                text=serialize_contract(publication) + "\n",
                            )
                        ]
                    )
                    value = contract_dict(publication)
                    action = "created"
                completed.append(
                    _summary(
                        item=item,
                        page=page,
                        action=action,
                        value=value,
                    )
                )
    except (
        ArtifactPublicationError,
        ExtractionCacheOperationError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        parser.error(
            "selective OCR stopped after "
            f"{len(completed)} completed pages: {error}"
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
