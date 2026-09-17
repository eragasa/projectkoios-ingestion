from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

from projectkoios.ingestion.batch import PdfBatchPlan
from projectkoios.ingestion.cache import _require_bounded_json_nesting
from projectkoios.ingestion.cli import (
    ArtifactPublicationError,
    ExtractionCacheOperationError,
    _publish_artifacts,
)
from projectkoios.ingestion.equation_batch_cli import _derive, _resolve_items
from projectkoios.ingestion.equation_enrichment import (
    DeterministicEquationAssembler,
    EquationIndexTier,
    Pix2TexCliEquationRecognizer,
    build_equation_index,
)
from projectkoios.ingestion.serialization import serialize_contract


class _EnrichmentTarget:
    def __init__(self, ingestion_directory: Path) -> None:
        root = ingestion_directory / "derived" / "equations"
        self.assembly = root / "assembly.json"
        self.recognition = root / "recognition.json"
        self.index = root / "index.json"
        existing = tuple(os.path.lexists(path) for path in self.paths)
        if any(existing) and not all(existing):
            raise ValueError("equation enrichment artifact set is incomplete")
        if all(existing) and any(
            path.is_symlink() or not path.is_file() for path in self.paths
        ):
            raise ValueError(
                "equation enrichment artifacts are not safe regular files"
            )
        self.existing = all(existing)

    @property
    def paths(self) -> tuple[Path, Path, Path]:
        return (self.assembly, self.recognition, self.index)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="koios-enrich-pdf-equations-batch")
    parser.add_argument("plan", type=Path)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--ingestion-root", type=Path, required=True)
    parser.add_argument("--cache-root", type=Path)
    parser.add_argument("--low-text-threshold", type=int, default=40)
    parser.add_argument("--pix2tex-executable", type=Path, required=True)
    parser.add_argument("--pix2tex-backend-version", required=True)
    parser.add_argument(
        "--pix2tex-resource",
        action="append",
        default=[],
        metavar="NAME=PATH",
    )
    parser.add_argument("--pix2tex-temperature", type=float, default=0.01)
    parser.add_argument("--pix2tex-timeout", type=int, default=900)
    parser.add_argument("--apply", action="store_true")
    return parser


def _resources(values: list[str]) -> tuple[tuple[str, Path], ...]:
    resources: list[tuple[str, Path]] = []
    for value in values:
        name, separator, raw_path = value.partition("=")
        if not separator or not name or not raw_path:
            raise ValueError("pix2tex resources must use NAME=PATH")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9._-]*", name):
            raise ValueError("pix2tex resource names must be portable")
        path = Path(raw_path).expanduser().resolve()
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"pix2tex resource is not a safe file: {name}")
        resources.append((name, path))
    names = tuple(name for name, _ in resources)
    if not names or len(names) != len(set(names)):
        raise ValueError("pix2tex resources must be non-empty and unique")
    return tuple(resources)


def _load_bounded_json(path: Path) -> dict[str, object]:
    content = path.read_bytes()
    if len(content) > 128_000_000:
        raise ValueError("equation enrichment artifact exceeds the size limit")
    text = content.decode("utf-8", errors="strict")
    _require_bounded_json_nesting(text)
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("equation enrichment artifact must be an object")
    return value


def _existing_summary(
    *,
    source_id: str,
    output_directory: str,
    candidate_count: int,
    assembly_artifact_id: str,
    assembly_count: int,
    target: _EnrichmentTarget,
    processor_identity_digest: str,
) -> dict[str, object]:
    recognition = _load_bounded_json(target.recognition)
    index = _load_bounded_json(target.index)
    proposals = recognition.get("proposals")
    records = index.get("records")
    if not isinstance(proposals, list) or not isinstance(records, list):
        raise ValueError("existing equation enrichment has an invalid shape")
    if recognition.get("assembly_artifact_id") != assembly_artifact_id:
        raise ValueError("existing recognition does not match assembly replay")
    if any(
        not isinstance(proposal, dict)
        or proposal.get("processor_identity_digest")
        != processor_identity_digest
        for proposal in proposals
    ):
        raise ValueError("existing recognition processor identity changed")
    recognition_artifact_id = recognition.get("artifact_id")
    index_artifact_id = index.get("artifact_id")
    if (
        not isinstance(recognition_artifact_id, str)
        or not isinstance(index_artifact_id, str)
        or index.get("assembly_artifact_id") != assembly_artifact_id
        or index.get("recognition_artifact_id") != recognition_artifact_id
        or index.get("source_id") != source_id
    ):
        raise ValueError("existing equation index linkage is inconsistent")
    tiers = {tier.value: 0 for tier in EquationIndexTier}
    for record in records:
        if not isinstance(record, dict) or record.get("tier") not in tiers:
            raise ValueError("existing equation index record is invalid")
        tiers[record["tier"]] += 1
    return {
        "source_id": source_id,
        "output_directory": output_directory,
        "action": "unchanged",
        "candidate_count": candidate_count,
        "assembly_count": assembly_count,
        "recognition_proposal_count": sum(
            isinstance(proposal, dict) and proposal.get("latex") is not None
            for proposal in proposals
        ),
        "index_tiers": tiers,
        "assembly_artifact_id": assembly_artifact_id,
        "recognition_artifact_id": recognition_artifact_id,
        "index_artifact_id": index_artifact_id,
        "assembly_artifact_sha256": hashlib.sha256(
            target.assembly.read_bytes()
        ).hexdigest(),
        "recognition_artifact_sha256": hashlib.sha256(
            target.recognition.read_bytes()
        ).hexdigest(),
        "index_artifact_sha256": hashlib.sha256(
            target.index.read_bytes()
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
        if not all(item.existing for item in resolved):
            raise ValueError(
                "equation detection artifacts must exist before enrichment"
            )
        targets = tuple(
            _EnrichmentTarget(item.ingestion_directory) for item in resolved
        )
        resources = _resources(args.pix2tex_resource)
        recognizer = Pix2TexCliEquationRecognizer(
            args.pix2tex_executable,
            backend_version=args.pix2tex_backend_version,
            resources=resources,
            temperature=args.pix2tex_temperature,
            timeout_seconds=args.pix2tex_timeout,
        )
    except (OSError, ValueError) as error:
        parser.error(f"invalid equation enrichment plan: {error}")

    if not args.apply:
        print(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "planned",
                    "processor_identity": recognizer.identity.identity_digest,
                    "items": [
                        {
                            "source_id": item.item.source_id,
                            "output_directory": (
                                item.item.output_directory.as_posix()
                            ),
                            "action": (
                                "verify_existing"
                                if target.existing
                                else "create"
                            ),
                        }
                        for item, target in zip(resolved, targets, strict=True)
                    ],
                },
                indent=2,
            )
        )
        return 2

    completed: list[dict[str, object]] = []
    try:
        for item, target in zip(resolved, targets, strict=True):
            detection, _, _ = _derive(
                item,
                cache_root=args.cache_root,
                low_text_threshold=args.low_text_threshold,
            )
            payload = item.pdf.read_bytes()
            if hashlib.sha256(payload).hexdigest() != item.item.sha256:
                raise ValueError(
                    "PDF source changed after enrichment preflight"
                )
            assembly = DeterministicEquationAssembler().assemble(
                detection, payload
            )
            assembly_text = serialize_contract(assembly) + "\n"
            if target.existing:
                if target.assembly.read_text(encoding="utf-8") != assembly_text:
                    raise ValueError(
                        "existing equation assembly differs from replay"
                    )
                completed.append(
                    _existing_summary(
                        source_id=item.item.source_id,
                        output_directory=(
                            item.item.output_directory.as_posix()
                        ),
                        candidate_count=len(detection.candidates),
                        assembly_artifact_id=assembly.artifact_id,
                        assembly_count=len(assembly.assemblies),
                        target=target,
                        processor_identity_digest=(
                            recognizer.identity.identity_digest
                        ),
                    )
                )
                continue
            recognition = recognizer.process(assembly)
            index = build_equation_index(assembly, recognition)
            texts = (
                assembly_text,
                serialize_contract(recognition) + "\n",
                serialize_contract(index) + "\n",
            )
            parent = target.assembly.parent
            if parent.resolve() != parent:
                raise ValueError(
                    "equation enrichment path changed after planning"
                )
            _publish_artifacts(list(zip(target.paths, texts, strict=True)))
            tiers = {
                tier.value: sum(record.tier is tier for record in index.records)
                for tier in EquationIndexTier
            }
            completed.append(
                {
                    "source_id": item.item.source_id,
                    "output_directory": item.item.output_directory.as_posix(),
                    "action": "created",
                    "candidate_count": len(detection.candidates),
                    "assembly_count": len(assembly.assemblies),
                    "recognition_proposal_count": sum(
                        proposal.latex is not None
                        for proposal in recognition.proposals
                    ),
                    "index_tiers": tiers,
                    "assembly_artifact_id": assembly.artifact_id,
                    "recognition_artifact_id": recognition.artifact_id,
                    "index_artifact_id": index.artifact_id,
                    "assembly_artifact_sha256": hashlib.sha256(
                        target.assembly.read_bytes()
                    ).hexdigest(),
                    "recognition_artifact_sha256": hashlib.sha256(
                        target.recognition.read_bytes()
                    ).hexdigest(),
                    "index_artifact_sha256": hashlib.sha256(
                        target.index.read_bytes()
                    ).hexdigest(),
                }
            )
    except (
        ArtifactPublicationError,
        ExtractionCacheOperationError,
        OSError,
        ValueError,
    ) as error:
        parser.error(
            "equation enrichment stopped after "
            f"{len(completed)} completed items: {error}"
        )
    print(
        json.dumps(
            {
                "schema_version": 1,
                "status": "completed",
                "processor_identity": recognizer.identity.identity_digest,
                "items": completed,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
