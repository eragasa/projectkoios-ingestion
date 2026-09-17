from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from projectkoios.ingestion.batch import PdfBatchItem, PdfBatchPlan
from projectkoios.ingestion.cache import _require_bounded_json_nesting
from projectkoios.ingestion.cli import (
    ArtifactPublicationError,
    ExtractionCacheOperationError,
    _publish_artifacts,
    extract_pdf_evidence,
)
from projectkoios.ingestion.equation_retrieval import (
    EquationRetrievalArtifact,
)
from projectkoios.ingestion.equations import (
    DeterministicEquationCandidateDetector,
    EquationDetectionResult,
)
from projectkoios.ingestion.serialization import (
    contract_dict,
    serialize_contract,
)

_MAX_EXTRACTION_ARTIFACT_BYTES = 128_000_000


@dataclass(frozen=True)
class _ResolvedItem:
    item: PdfBatchItem
    pdf: Path
    ingestion_directory: Path
    extraction_artifact: Path
    extraction_artifact_sha256: str
    detection_artifact: Path
    retrieval_artifact: Path
    existing: bool


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="koios-detect-pdf-equations-batch")
    parser.add_argument("plan", type=Path)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--ingestion-root", type=Path, required=True)
    parser.add_argument("--cache-root", type=Path)
    parser.add_argument("--low-text-threshold", type=int, default=40)
    parser.add_argument("--apply", action="store_true")
    return parser


def _resolve_items(
    plan: PdfBatchPlan,
    *,
    source_root: Path,
    ingestion_root: Path,
) -> tuple[_ResolvedItem, ...]:
    source_root = source_root.expanduser().resolve()
    ingestion_root = ingestion_root.expanduser().resolve()
    if not source_root.is_dir():
        raise ValueError("source root must be an existing directory")
    if not ingestion_root.is_dir():
        raise ValueError("ingestion root must be an existing directory")
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

        raw_ingestion_directory = ingestion_root / Path(item.output_directory)
        if raw_ingestion_directory.is_symlink():
            raise ValueError(
                "ingestion directory cannot be a symlink: "
                f"{item.output_directory}"
            )
        ingestion_directory = raw_ingestion_directory.resolve()
        if not ingestion_directory.is_relative_to(ingestion_root):
            raise ValueError(
                f"ingestion directory escapes root: {item.output_directory}"
            )
        if not ingestion_directory.is_dir():
            raise ValueError(
                f"ingestion directory does not exist: {item.output_directory}"
            )
        extraction_artifact = ingestion_directory / "extraction.json"
        if (
            extraction_artifact.is_symlink()
            or not extraction_artifact.is_file()
        ):
            raise ValueError(
                "raw extraction artifact is missing or unsafe: "
                f"{item.output_directory}"
            )
        extraction_artifact_sha256 = _validate_extraction_identity(
            extraction_artifact, item
        )

        derived = ingestion_directory / "derived" / "equations"
        detection_artifact = derived / "detection.json"
        retrieval_artifact = derived / "retrieval.json"
        detection_exists = os.path.lexists(detection_artifact)
        retrieval_exists = os.path.lexists(retrieval_artifact)
        if detection_exists != retrieval_exists:
            raise ValueError(
                f"equation artifact set is incomplete: {item.output_directory}"
            )
        if detection_exists and (
            detection_artifact.is_symlink()
            or retrieval_artifact.is_symlink()
            or not detection_artifact.is_file()
            or not retrieval_artifact.is_file()
        ):
            raise ValueError(
                "equation artifacts are not safe regular files: "
                f"{item.output_directory}"
            )
        resolved.append(
            _ResolvedItem(
                item=item,
                pdf=pdf,
                ingestion_directory=ingestion_directory,
                extraction_artifact=extraction_artifact,
                extraction_artifact_sha256=extraction_artifact_sha256,
                detection_artifact=detection_artifact,
                retrieval_artifact=retrieval_artifact,
                existing=detection_exists,
            )
        )
    return tuple(resolved)


def _validate_extraction_identity(path: Path, item: PdfBatchItem) -> str:
    content = path.read_bytes()
    if len(content) > _MAX_EXTRACTION_ARTIFACT_BYTES:
        raise ValueError("raw extraction artifact exceeds the size limit")
    try:
        text = content.decode("utf-8", errors="strict")
        _require_bounded_json_nesting(text)
        value = json.loads(text)
        document = value["document"]
        source = document["source"]
        manifest = value["manifest"]
    except (
        KeyError,
        TypeError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        ValueError,
    ) as error:
        raise ValueError(
            "raw extraction artifact has an invalid shape"
        ) from error
    if (
        not isinstance(document, dict)
        or not isinstance(source, dict)
        or not isinstance(manifest, dict)
    ):
        raise ValueError("raw extraction artifact has an invalid shape")
    if (
        source.get("source_id") != item.source_id
        or source.get("content_hash") != item.sha256
        or source.get("byte_length") != item.byte_size
        or manifest.get("source_id") != item.source_id
        or manifest.get("source_content_hash") != item.sha256
        or manifest.get("status") != "completed"
    ):
        raise ValueError(
            "raw extraction identity does not match the batch plan"
        )
    return hashlib.sha256(content).hexdigest()


def _planned_summary(items: tuple[_ResolvedItem, ...]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "status": "planned",
        "items": [
            {
                "source_id": resolved.item.source_id,
                "output_directory": resolved.item.output_directory.as_posix(),
                "action": "verify_existing" if resolved.existing else "create",
                "detection_artifact": (
                    resolved.item.output_directory
                    / "derived/equations/detection.json"
                ).as_posix(),
                "retrieval_artifact": (
                    resolved.item.output_directory
                    / "derived/equations/retrieval.json"
                ).as_posix(),
            }
            for resolved in items
        ],
    }


def _derive(
    item: _ResolvedItem, *, cache_root: Path | None, low_text_threshold: int
) -> tuple[EquationDetectionResult, EquationRetrievalArtifact, str]:
    artifact_parent = item.detection_artifact.parent
    if artifact_parent.resolve() != artifact_parent or any(
        path.is_symlink()
        for path in (item.detection_artifact, item.retrieval_artifact)
    ):
        raise ValueError("equation artifact path changed after planning")
    payload, extraction = extract_pdf_evidence(
        item.pdf,
        source_id=item.item.source_id,
        cache_root=cache_root,
        locator=item.item.locator or item.item.pdf_path.as_posix(),
        low_text_threshold=low_text_threshold,
        expected_source_sha256=item.item.sha256,
        expected_source_byte_size=item.item.byte_size,
    )
    extraction_bytes = item.extraction_artifact.read_bytes()
    if (
        hashlib.sha256(extraction_bytes).hexdigest()
        != item.extraction_artifact_sha256
    ):
        raise ValueError("raw extraction artifact changed after preflight")
    existing_extraction = json.loads(extraction_bytes)
    replayed_extraction = contract_dict(extraction)
    if existing_extraction.get("document") != replayed_extraction["document"]:
        raise ValueError("raw extraction document changed after preflight")
    detection = DeterministicEquationCandidateDetector().detect(
        extraction.document,
        BytesIO(payload),
    )
    retrieval = EquationRetrievalArtifact.from_detection(detection)
    detection_text = serialize_contract(detection) + "\n"
    retrieval_text = serialize_contract(retrieval) + "\n"
    action = "created"
    if item.existing:
        if (
            item.detection_artifact.read_text(encoding="utf-8")
            != detection_text
            or item.retrieval_artifact.read_text(encoding="utf-8")
            != retrieval_text
        ):
            raise ValueError("existing equation artifacts differ from replay")
        action = "unchanged"
    else:
        _publish_artifacts(
            [
                (item.detection_artifact, detection_text),
                (item.retrieval_artifact, retrieval_text),
            ]
        )
    return detection, retrieval, action


def _completed_item(
    item: _ResolvedItem,
    detection: EquationDetectionResult,
    retrieval: EquationRetrievalArtifact,
    action: str,
) -> dict[str, object]:
    display_count = sum(
        candidate.kind.value == "display" for candidate in detection.candidates
    )
    return {
        "source_id": item.item.source_id,
        "output_directory": item.item.output_directory.as_posix(),
        "action": action,
        "detection_artifact": (
            item.item.output_directory / "derived/equations/detection.json"
        ).as_posix(),
        "retrieval_artifact": (
            item.item.output_directory / "derived/equations/retrieval.json"
        ).as_posix(),
        "detection_result_id": detection.result_id,
        "retrieval_artifact_id": retrieval.artifact_id,
        "candidate_count": len(detection.candidates),
        "display_candidate_count": display_count,
        "inline_candidate_count": len(detection.candidates) - display_count,
        "warning_count": len(detection.warnings),
        "transcription_status": "native_text_only",
        "detection_artifact_sha256": hashlib.sha256(
            item.detection_artifact.read_bytes()
        ).hexdigest(),
        "retrieval_artifact_sha256": hashlib.sha256(
            item.retrieval_artifact.read_bytes()
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
            ingestion_root=args.ingestion_root,
        )
    except (OSError, ValueError) as error:
        parser.error(f"invalid equation batch plan: {error}")
    if not args.apply:
        print(json.dumps(_planned_summary(resolved), indent=2))
        return 2

    completed: list[dict[str, object]] = []
    ingestion_root = args.ingestion_root.expanduser().resolve()
    try:
        for item in resolved:
            current_directory = item.ingestion_directory.resolve()
            if (
                not current_directory.is_relative_to(ingestion_root)
                or current_directory != item.ingestion_directory
            ):
                raise ValueError("ingestion path changed after planning")
            detection, retrieval, action = _derive(
                item,
                cache_root=args.cache_root,
                low_text_threshold=args.low_text_threshold,
            )
            completed.append(
                _completed_item(item, detection, retrieval, action)
            )
    except (
        ArtifactPublicationError,
        ExtractionCacheOperationError,
        OSError,
        ValueError,
    ) as error:
        parser.error(
            "equation batch stopped after "
            f"{len(completed)} completed items: {error}"
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
