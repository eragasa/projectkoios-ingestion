from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from projectkoios.ingestion.article_structure import (
    DeterministicArticleStructureAnalyzer,
)
from projectkoios.ingestion.batch import PdfBatchPlan
from projectkoios.ingestion.cli import (
    ArtifactPublicationError,
    ExtractionCacheOperationError,
    _publish_artifacts,
    extract_pdf_evidence,
)
from projectkoios.ingestion.equation_batch_cli import (
    _resolve_items,
    _ResolvedItem,
)
from projectkoios.ingestion.equations import (
    DeterministicEquationCandidateDetector,
)
from projectkoios.ingestion.figures import DeterministicFigureCandidateDetector
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout import DeterministicLayoutProcessor
from projectkoios.ingestion.provenance import (
    DerivationAuditInput,
    DerivationAuditValidator,
)
from projectkoios.ingestion.reference_evidence import (
    build_reference_evidence,
    serialize_reference_evidence,
)
from projectkoios.ingestion.serialization import (
    contract_dict,
    serialize_contract,
)
from projectkoios.ingestion.table_structure import (
    DeterministicTableStructureReconstructor,
)
from projectkoios.ingestion.tables import DeterministicTableCandidateDetector
from projectkoios.ingestion.transcript_projection import (
    DeterministicCleanTranscriptProjector,
)
from projectkoios.ingestion.transcription import (
    DeterministicStructuredTranscriptionComposer,
    TranscriptionInput,
)

TRANSCRIPT_BATCH_MANIFEST_SCHEMA_VERSION = 2


@dataclass(frozen=True)
class _TranscriptTarget:
    root: Path
    clean_artifact: Path
    clean_text: Path
    audit_artifact: Path
    reference_evidence: Path
    manifest: Path
    existing: bool

    @classmethod
    def resolve(cls, ingestion_directory: Path) -> _TranscriptTarget:
        root = ingestion_directory / "derived" / "transcription"
        target = cls(
            root=root,
            clean_artifact=root / "clean.json",
            clean_text=root / "clean.txt",
            audit_artifact=root / "audit.json",
            reference_evidence=root / "reference-evidence.json",
            manifest=root / "manifest.json",
            existing=False,
        )
        existence = tuple(os.path.lexists(path) for path in target.paths)
        if any(existence) and not all(existence):
            raise ValueError("transcription artifact set is incomplete")
        if all(existence) and any(
            path.is_symlink() or not path.is_file() for path in target.paths
        ):
            raise ValueError(
                "transcription artifacts are not safe regular files"
            )
        return cls(
            root=target.root,
            clean_artifact=target.clean_artifact,
            clean_text=target.clean_text,
            audit_artifact=target.audit_artifact,
            reference_evidence=target.reference_evidence,
            manifest=target.manifest,
            existing=all(existence),
        )

    @property
    def paths(self) -> tuple[Path, Path, Path, Path, Path]:
        return (
            self.clean_artifact,
            self.clean_text,
            self.audit_artifact,
            self.reference_evidence,
            self.manifest,
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="koios-compose-pdf-transcripts-batch")
    parser.add_argument("plan", type=Path)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--ingestion-root", type=Path, required=True)
    parser.add_argument("--cache-root", type=Path)
    parser.add_argument("--low-text-threshold", type=int, default=40)
    parser.add_argument("--apply", action="store_true")
    return parser


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _manifest_text(
    item: _ResolvedItem,
    *,
    extraction_manifest_id: str,
    layout_result_ids: tuple[str, ...],
    structure_analysis_id: str,
    equation_result_id: str,
    table_detection_result_id: str,
    table_structure_result_id: str,
    figure_result_id: str,
    transcription_result_id: str,
    clean_artifact_id: str,
    clean_artifact_sha256: str,
    clean_text_sha256: str,
    audit_report_id: str,
    audit_artifact_sha256: str,
    reference_evidence_record_id: str,
    reference_evidence_sha256: str,
    counts: dict[str, int],
) -> str:
    manifest_id = stable_id(
        "pdf-transcription-batch-manifest",
        TRANSCRIPT_BATCH_MANIFEST_SCHEMA_VERSION,
        item.item.source_id,
        item.item.sha256,
        item.extraction_artifact_sha256,
        extraction_manifest_id,
        layout_result_ids,
        structure_analysis_id,
        equation_result_id,
        table_detection_result_id,
        table_structure_result_id,
        figure_result_id,
        transcription_result_id,
        clean_artifact_id,
        clean_artifact_sha256,
        clean_text_sha256,
        audit_report_id,
        audit_artifact_sha256,
        reference_evidence_record_id,
        reference_evidence_sha256,
        tuple(sorted(counts.items())),
    )
    value: dict[str, object] = {
        "schema_version": TRANSCRIPT_BATCH_MANIFEST_SCHEMA_VERSION,
        "manifest_id": manifest_id,
        "source_id": item.item.source_id,
        "source_sha256": item.item.sha256,
        "source_byte_size": item.item.byte_size,
        "raw_extraction_artifact_sha256": item.extraction_artifact_sha256,
        "extraction_manifest_id": extraction_manifest_id,
        "layout_result_ids": list(layout_result_ids),
        "structure_analysis_id": structure_analysis_id,
        "equation_detection_result_id": equation_result_id,
        "table_detection_result_id": table_detection_result_id,
        "table_structure_result_id": table_structure_result_id,
        "figure_detection_result_id": figure_result_id,
        "structured_transcription_result_id": transcription_result_id,
        "clean_transcript_artifact_id": clean_artifact_id,
        "clean_transcript_artifact_sha256": clean_artifact_sha256,
        "clean_text_sha256": clean_text_sha256,
        "derivation_audit_report_id": audit_report_id,
        "derivation_audit_artifact_sha256": audit_artifact_sha256,
        "reference_evidence_record_id": reference_evidence_record_id,
        "reference_evidence_sha256": reference_evidence_sha256,
        "counts": dict(sorted(counts.items())),
        "status": "automated_unreviewed",
        "intermediate_policy": (
            "deterministically_reconstructible_not_materialized"
        ),
        "limitations": [
            "not_human_proofread",
            "not_semantically_corrected",
            "not_scientifically_validated",
            "layout_reading_order_is_proposed",
        ],
    }
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


def _derive(
    item: _ResolvedItem,
    target: _TranscriptTarget,
    *,
    cache_root: Path | None,
    low_text_threshold: int,
) -> tuple[tuple[str, str, str, str, str], dict[str, object]]:
    if target.root.resolve() != target.root or any(
        path.is_symlink() for path in target.paths
    ):
        raise ValueError("transcription artifact path changed after planning")
    payload, extraction = extract_pdf_evidence(
        item.pdf,
        source_id=item.item.source_id,
        cache_root=cache_root,
        locator=item.item.locator or item.item.pdf_path.as_posix(),
        low_text_threshold=low_text_threshold,
        expected_source_sha256=item.item.sha256,
        expected_source_byte_size=item.item.byte_size,
    )
    if hashlib.sha256(payload).hexdigest() != item.item.sha256:
        raise ValueError("PDF source changed after transcript preflight")
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

    document = extraction.document
    layouts = DeterministicLayoutProcessor().analyze(document)
    structure = DeterministicArticleStructureAnalyzer().analyze(document)
    equations = DeterministicEquationCandidateDetector().detect_with_layout(
        document, BytesIO(payload), layouts
    )
    if not item.existing:
        raise ValueError("equation detection artifacts must already exist")
    if item.detection_artifact.read_text(encoding="utf-8") != (
        serialize_contract(equations) + "\n"
    ):
        raise ValueError("equation detection differs from transcript replay")
    table_detection = DeterministicTableCandidateDetector().detect_with_layout(
        document, BytesIO(payload), layouts
    )
    tables = DeterministicTableStructureReconstructor().reconstruct(
        table_detection
    )
    figures = DeterministicFigureCandidateDetector().detect_with_layout(
        document, BytesIO(payload), layouts
    )
    transcription = DeterministicStructuredTranscriptionComposer().compose(
        TranscriptionInput.create(
            document=document,
            structure_analysis=structure,
            equation_detection_result=equations,
            table_structure_result=tables,
            figure_detection_result=figures,
        )
    )
    clean = DeterministicCleanTranscriptProjector().project(
        transcription, layouts
    )
    audit = DerivationAuditValidator().audit(
        DerivationAuditInput(
            source_content=payload,
            extraction_result=extraction,
            layout_results=layouts,
            structure_analyses=(structure,),
            equation_results=(equations,),
            table_detection_results=(table_detection,),
            table_structure_results=(tables,),
            figure_results=(figures,),
            transcription_results=(transcription,),
            clean_transcript_artifacts=(clean,),
        )
    )
    audit.require_valid()

    clean_artifact_text = serialize_contract(clean) + "\n"
    clean_text = clean.text
    audit_text = serialize_contract(audit) + "\n"
    reference_evidence = build_reference_evidence(
        extraction_result=extraction,
        extraction_artifact=extraction_bytes,
        clean_transcript=clean,
        clean_transcript_artifact=clean_artifact_text.encode("utf-8"),
        derivation_audit=audit,
        derivation_audit_artifact=audit_text.encode("utf-8"),
    )
    reference_evidence_bytes = serialize_reference_evidence(reference_evidence)
    reference_evidence_text = reference_evidence_bytes.decode("utf-8")
    if structure.analysis_id is None:
        raise ValueError("article structure analysis has no stable identity")
    counts = {
        "clean_blocks": len(clean.blocks),
        "clean_exclusions": len(clean.exclusions),
        "clean_pages": len(clean.pages),
        "equation_candidates": len(equations.candidates),
        "figure_candidates": len(figures.candidates),
        "source_blocks": sum(len(page.blocks) for page in document.pages),
        "source_pages": len(document.pages),
        "structure_nodes": len(structure.nodes),
        "table_candidates": len(table_detection.candidates),
        "transcription_items": len(transcription.items),
        "transcription_omissions": len(transcription.omissions),
        "transcription_warnings": len(transcription.warnings),
    }
    manifest_text = _manifest_text(
        item,
        extraction_manifest_id=extraction.manifest.manifest_id,
        layout_result_ids=tuple(layout.result_id for layout in layouts),
        structure_analysis_id=structure.analysis_id,
        equation_result_id=equations.result_id,
        table_detection_result_id=table_detection.result_id,
        table_structure_result_id=tables.result_id,
        figure_result_id=figures.result_id,
        transcription_result_id=transcription.result_id,
        clean_artifact_id=clean.artifact_id,
        clean_artifact_sha256=_sha256_text(clean_artifact_text),
        clean_text_sha256=_sha256_text(clean_text),
        audit_report_id=audit.report_id,
        audit_artifact_sha256=_sha256_text(audit_text),
        reference_evidence_record_id=reference_evidence.record_id,
        reference_evidence_sha256=hashlib.sha256(
            reference_evidence_bytes
        ).hexdigest(),
        counts=counts,
    )
    texts = (
        clean_artifact_text,
        clean_text,
        audit_text,
        reference_evidence_text,
        manifest_text,
    )
    action = "created"
    if target.existing:
        for path, expected in zip(target.paths, texts, strict=True):
            if path.read_text(encoding="utf-8") != expected:
                raise ValueError(
                    "existing transcription artifact differs from replay: "
                    f"{path.name}"
                )
        action = "unchanged"
    else:
        _publish_artifacts(list(zip(target.paths, texts, strict=True)))
    manifest = json.loads(manifest_text)
    summary: dict[str, object] = {
        "source_id": item.item.source_id,
        "output_directory": item.item.output_directory.as_posix(),
        "action": action,
        "manifest_id": manifest["manifest_id"],
        "transcript_batch_manifest_schema_version": (
            TRANSCRIPT_BATCH_MANIFEST_SCHEMA_VERSION
        ),
        "clean_transcript_artifact_id": clean.artifact_id,
        "clean_text_sha256": clean.text_sha256,
        "derivation_audit_report_id": audit.report_id,
        "audit_status": audit.status.value,
        "reference_evidence_record_id": reference_evidence.record_id,
        "reference_evidence_sha256": hashlib.sha256(
            reference_evidence_bytes
        ).hexdigest(),
        "counts": counts,
    }
    return texts, summary


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
                "equation detection artifacts must exist before transcription"
            )
        targets = tuple(
            _TranscriptTarget.resolve(item.ingestion_directory)
            for item in resolved
        )
    except (OSError, ValueError) as error:
        parser.error(f"invalid transcription batch plan: {error}")

    if not args.apply:
        print(
            json.dumps(
                {
                    "schema_version": 1,
                    "transcript_batch_manifest_schema_version": (
                        TRANSCRIPT_BATCH_MANIFEST_SCHEMA_VERSION
                    ),
                    "status": "planned",
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
    ingestion_root = args.ingestion_root.expanduser().resolve()
    try:
        for item, target in zip(resolved, targets, strict=True):
            current_directory = item.ingestion_directory.resolve()
            if (
                not current_directory.is_relative_to(ingestion_root)
                or current_directory != item.ingestion_directory
            ):
                raise ValueError("ingestion path changed after planning")
            _, summary = _derive(
                item,
                target,
                cache_root=args.cache_root,
                low_text_threshold=args.low_text_threshold,
            )
            completed.append(summary)
    except (
        ArtifactPublicationError,
        ExtractionCacheOperationError,
        OSError,
        ValueError,
    ) as error:
        parser.error(
            "transcription batch stopped after "
            f"{len(completed)} completed items: {error}"
        )
    print(
        json.dumps(
            {
                "schema_version": 1,
                "transcript_batch_manifest_schema_version": (
                    TRANSCRIPT_BATCH_MANIFEST_SCHEMA_VERSION
                ),
                "status": "completed",
                "items": completed,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
