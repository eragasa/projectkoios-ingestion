"""Create-once selective reconciliation of published OCR page evidence."""

from __future__ import annotations

import argparse
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from projectkoios.ingestion.cache import (
    _require_bounded_json_nesting,
    deserialize_extraction_result,
)
from projectkoios.ingestion.cli import (
    ArtifactPublicationError,
    _publish_artifacts,
)
from projectkoios.ingestion.ocr.batch.publication import SelectiveOCRPublication
from projectkoios.ingestion.ocr.reconciliation.batch.item import (
    SelectiveOCRReconciliationItem,
)
from projectkoios.ingestion.ocr.reconciliation.batch.page import (
    SelectiveOCRReconciliationPage,
)
from projectkoios.ingestion.ocr.reconciliation.batch.plan import (
    SelectiveOCRReconciliationPlan,
)
from projectkoios.ingestion.ocr.reconciliation.batch.publication import (
    SelectiveOCRReconciliationPublication,
)
from projectkoios.ingestion.reconciliation.reconciler import (
    DeterministicOCRReconciler,
)
from projectkoios.ingestion.reconciliation.request import (
    OCRReconciliationRequest,
)
from projectkoios.ingestion.serialization import (
    contract_dict,
    serialize_contract,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.verifier import SHA256Verifier
from projectkoios.ingestion.storage.artifact import ArtifactPublicationItem

_MAX_PLAN_BYTES = 8_000_000
_MAX_EXTRACTION_BYTES = 64_000_000
_MAX_OCR_PUBLICATION_BYTES = 64_000_000
_MAX_RECONCILIATION_PUBLICATION_BYTES = 65_536_000


@dataclass(frozen=True, slots=True)
class _ResolvedPage:
    contract: SelectiveOCRReconciliationPage
    ocr_artifact: Path
    output_artifact: Path
    existing: bool


@dataclass(frozen=True, slots=True)
class _ResolvedItem:
    contract: SelectiveOCRReconciliationItem
    extraction_artifact: Path
    pages: tuple[_ResolvedPage, ...]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.ocr_reconciliation_batch"
    )
    parser.add_argument("plan", type=Path)
    parser.add_argument("--ingestion-root", type=Path, required=True)
    parser.add_argument("--ocr-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
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
    path: Path, label: str, *, require_private: bool = False
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


def _safe_existing_member(
    root: Path, relative: PurePosixPath, label: str
) -> Path:
    candidate = (root / Path(relative)).absolute()
    if candidate.is_symlink() or candidate.resolve() != candidate:
        raise ValueError(f"{label} cannot traverse symlinks")
    if root not in candidate.parents:
        raise ValueError(f"{label} escapes its root")
    if not candidate.is_file():
        raise ValueError(f"{label} is missing")
    return candidate


def _safe_output_artifact(
    root: Path,
    directory: PurePosixPath,
    page_index: int,
) -> Path:
    page_directory = Path(directory) / f"page-{page_index + 1:06d}"
    candidate_directory = (root / page_directory).absolute()
    if not candidate_directory.is_relative_to(root):
        raise ValueError("reconciliation output escapes its root")
    current = root
    for part in page_directory.parts:
        current = current / part
        if os.path.lexists(current):
            if current.is_symlink() or not current.is_dir():
                raise ValueError("reconciliation output path is unsafe")
            if stat.S_IMODE(current.stat().st_mode) & 0o077:
                raise ValueError(
                    "reconciliation output directories must be private"
                )
    artifact = candidate_directory / "result.json"
    if os.path.lexists(artifact):
        if artifact.is_symlink() or not artifact.is_file():
            raise ValueError("reconciliation output artifact is unsafe")
        if stat.S_IMODE(artifact.stat().st_mode) != 0o600:
            raise ValueError(
                "reconciliation output artifact must have mode 0600"
            )
    return artifact


def _sha256(path: Path, maximum: int, label: str) -> str:
    return SHA256Fingerprinter.fingerprint(
        content=_read_bounded(path, maximum, label)
    )


def _resolve_plan(
    plan: SelectiveOCRReconciliationPlan,
    *,
    ingestion_root: Path,
    ocr_root: Path,
    output_root: Path,
) -> tuple[_ResolvedItem, ...]:
    resolved: list[_ResolvedItem] = []
    destinations: set[Path] = set()
    for item in plan.items:
        extraction = _safe_existing_member(
            ingestion_root,
            item.source.output_directory / "extraction.json",
            "native extraction artifact",
        )
        if _sha256(
            extraction, _MAX_EXTRACTION_BYTES, "native extraction artifact"
        ) != (item.extraction_sha256):
            raise ValueError("native extraction artifact SHA-256 changed")
        pages: list[_ResolvedPage] = []
        for page in item.pages:
            ocr_artifact = _safe_existing_member(
                ocr_root,
                item.ocr_directory
                / f"page-{page.page_index + 1:06d}"
                / "result.json",
                "selective OCR publication",
            )
            if stat.S_IMODE(ocr_artifact.stat().st_mode) != 0o600:
                raise ValueError(
                    "selective OCR publication must have mode 0600"
                )
            if (
                _sha256(
                    ocr_artifact,
                    _MAX_OCR_PUBLICATION_BYTES,
                    "selective OCR publication",
                )
                != page.ocr_publication_sha256
            ):
                raise ValueError("selective OCR publication SHA-256 changed")
            output_artifact = _safe_output_artifact(
                output_root,
                item.output_directory,
                page.page_index,
            )
            if output_artifact in destinations:
                raise ValueError(
                    "reconciliation plan has duplicate destinations"
                )
            destinations.add(output_artifact)
            if output_artifact.exists() and (
                output_artifact.is_symlink() or not output_artifact.is_file()
            ):
                raise ValueError("existing reconciliation output is unsafe")
            pages.append(
                _ResolvedPage(
                    contract=page,
                    ocr_artifact=ocr_artifact,
                    output_artifact=output_artifact,
                    existing=output_artifact.is_file(),
                )
            )
        resolved.append(
            _ResolvedItem(
                contract=item,
                extraction_artifact=extraction,
                pages=tuple(pages),
            )
        )
    return tuple(resolved)


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
    if type(value) is not dict:
        raise ValueError(f"{label} must contain a JSON object")
    return value


def _ocr_publication(
    item: SelectiveOCRReconciliationItem,
    page: SelectiveOCRReconciliationPage,
    artifact: Path,
) -> SelectiveOCRPublication:
    content = _read_bounded(
        artifact,
        _MAX_OCR_PUBLICATION_BYTES,
        "selective OCR publication",
    )
    if not SHA256Verifier.verify(
        content=content, expected=page.ocr_publication_sha256
    ):
        raise ValueError("selective OCR publication changed after preflight")
    publication = SelectiveOCRPublication.from_dict(
        _load_json(content, "selective OCR publication")
    )
    selection = publication.result.request.selections[0]
    region = selection.image.rendered_region
    if (
        publication.source_sha256 != item.source.sha256
        or publication.extraction_sha256 != item.extraction_sha256
        or publication.page_index != page.page_index
        or region.source_id != item.source.source_id
        or region.source_blob_id != f"blob:sha256:{item.source.sha256}"
    ):
        raise ValueError("selective OCR publication linkage is inconsistent")
    if selection.native_text_blocks:
        raise ValueError(
            "selective reconciliation currently requires OCR evidence without "
            "native text references"
        )
    return publication


def _validate_existing(
    path: Path,
    expected: SelectiveOCRReconciliationPublication,
) -> None:
    content = _read_bounded(
        path,
        _MAX_RECONCILIATION_PUBLICATION_BYTES,
        "reconciliation publication",
    )
    if _load_json(content, "reconciliation publication") != contract_dict(
        expected
    ):
        raise ValueError("existing reconciliation publication is inconsistent")


def main(arguments: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(arguments)
    try:
        plan_text = _read_bounded(
            args.plan.expanduser().absolute(),
            _MAX_PLAN_BYTES,
            "reconciliation plan",
        ).decode("utf-8", errors="strict")
        _require_bounded_json_nesting(plan_text)
        plan = SelectiveOCRReconciliationPlan.from_json(plan_text)
        ingestion_root = _safe_root(args.ingestion_root, "ingestion root")
        ocr_root = _safe_root(args.ocr_root, "OCR root", require_private=True)
        output_root = _safe_root(
            args.output_root,
            "reconciliation output root",
            require_private=True,
        )
        if output_root in (ingestion_root, ocr_root):
            raise ValueError("reconciliation output root must be separate")
        resolved = _resolve_plan(
            plan,
            ingestion_root=ingestion_root,
            ocr_root=ocr_root,
            output_root=output_root,
        )
    except (OSError, TypeError, UnicodeDecodeError, ValueError) as error:
        parser.error(f"invalid reconciliation plan: {error}")

    if not args.apply:
        print(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "planned",
                    "reconciliation_execution": "not_executed",
                    "items": [
                        {
                            "source_id": item.contract.source.source_id,
                            "page_index": page.contract.page_index,
                            "action": "verify_existing"
                            if page.existing
                            else "create",
                        }
                        for item in resolved
                        for page in item.pages
                    ],
                },
                indent=2,
            )
        )
        return 2

    reconciler = DeterministicOCRReconciler()
    completed: list[dict[str, object]] = []
    try:
        for item in resolved:
            extraction_content = _read_bounded(
                item.extraction_artifact,
                _MAX_EXTRACTION_BYTES,
                "native extraction artifact",
            )
            if not SHA256Verifier.verify(
                content=extraction_content,
                expected=item.contract.extraction_sha256,
            ):
                raise ValueError("native extraction changed after preflight")
            extraction = deserialize_extraction_result(
                extraction_content.decode("utf-8", errors="strict")
            )
            source = extraction.document.source
            if (
                source.source_id != item.contract.source.source_id
                or source.content_hash != item.contract.source.sha256
                or source.byte_length != item.contract.source.byte_size
            ):
                raise ValueError(
                    "native extraction source linkage is inconsistent"
                )
            for page in item.pages:
                if page.contract.page_index >= len(extraction.document.pages):
                    raise ValueError("reconciliation page is out of bounds")
                ocr_publication = _ocr_publication(
                    item.contract,
                    page.contract,
                    page.ocr_artifact,
                )
                request = OCRReconciliationRequest.create(
                    ocr_result=ocr_publication.result,
                    selection_index=0,
                )
                result = reconciler.action(request=request)
                publication = SelectiveOCRReconciliationPublication.create(
                    item=item.contract,
                    page=page.contract,
                    result=result,
                )
                current = _safe_output_artifact(
                    output_root,
                    item.contract.output_directory,
                    page.contract.page_index,
                )
                if current != page.output_artifact:
                    raise ValueError(
                        "reconciliation output changed after preflight"
                    )
                if page.existing:
                    _validate_existing(page.output_artifact, publication)
                    action = "unchanged"
                else:
                    _publish_artifacts(
                        (
                            ArtifactPublicationItem(
                                path=page.output_artifact,
                                text=serialize_contract(publication) + "\n",
                            ),
                        )
                    )
                    action = "created"
                completed.append(
                    {
                        "source_id": item.contract.source.source_id,
                        "page_index": page.contract.page_index,
                        "action": action,
                        "publication_id": publication.publication_id,
                        "result_id": result.result_id,
                        "native_item_count": len(result.native_segments),
                        "ocr_item_count": len(result.ocr_stream),
                        "proposed_item_count": len(
                            result.proposed_merged_stream
                        ),
                        "warning_count": len(result.warnings),
                        "artifact": page.output_artifact.relative_to(
                            output_root
                        ).as_posix(),
                        "artifact_sha256": _sha256(
                            page.output_artifact,
                            _MAX_RECONCILIATION_PUBLICATION_BYTES,
                            "reconciliation publication",
                        ),
                    }
                )
    except (
        ArtifactPublicationError,
        OSError,
        TypeError,
        UnicodeDecodeError,
        ValueError,
    ) as error:
        parser.error(
            "selective reconciliation stopped after "
            f"{len(completed)} completed pages: {error}"
        )
    print(
        json.dumps(
            {"schema_version": 1, "status": "completed", "items": completed},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
