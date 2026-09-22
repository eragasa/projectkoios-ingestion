from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any

from projectkoios.ingestion.article_structure import (
    DeterministicArticleStructureAnalyzer,
)
from projectkoios.ingestion.batch import PdfBatchItem, PdfBatchPlan
from projectkoios.ingestion.cli import extract_pdf_evidence
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
from projectkoios.ingestion.serialization import (
    contract_dict,
    serialize_contract,
)
from projectkoios.ingestion.table_structure import (
    DeterministicTableStructureReconstructor,
)
from projectkoios.ingestion.tables import DeterministicTableCandidateDetector
from projectkoios.ingestion.transcript_v2 import (
    CLEAN_TRANSCRIPT_V2_ARTIFACT_GENERATION,
    CLEAN_TRANSCRIPT_V2_CONTRACT_ID,
    CLEAN_TRANSCRIPT_V2_CONTRACT_VERSION,
    CLEAN_TRANSCRIPT_V2_PROCESSOR_VERSION,
    CleanTranscriptV2Configuration,
    DeterministicCleanTranscriptV2Projector,
    PublisherFrontMatterKind,
)
from projectkoios.ingestion.transcription import (
    DeterministicStructuredTranscriptionComposer,
    TranscriptionInput,
)

TRANSCRIPT_V2_BATCH_PLAN_CONTRACT_ID = (
    "projectkoios.ingestion.transcript-batch-plan"
)
TRANSCRIPT_V2_BATCH_PLAN_CONTRACT_VERSION = "0.1.0"
TRANSCRIPT_V2_BATCH_PLAN_SCHEMA_VERSION = 1
TRANSCRIPT_V2_BATCH_MANIFEST_SCHEMA_VERSION = 1
TRANSCRIPT_V2_OUTPUT_RELATIVE_PATH = PurePosixPath(
    "derived/transcription/generation-2"
)
_MAX_PLAN_BYTES = 4_000_000
_MAX_ARTIFACT_BYTES = 128_000_000
_MAX_ITEMS = 256
_MAX_IDENTITY_LENGTH = 4_096
_SHA256_LENGTH = 64
_OUTPUT_NAMES = ("audit.json", "clean.json", "clean.txt", "manifest.json")


def _batch_item_id(
    *,
    source_id: str,
    pdf_path: PurePosixPath,
    output_directory: PurePosixPath,
    source_sha256: str,
    source_byte_size: int,
    locator: str | None,
    extraction_artifact_sha256: str,
    extraction_manifest_id: str,
    equation_detection_artifact_sha256: str,
    equation_detection_result_id: str,
) -> str:
    return stable_id(
        "transcript-v2-batch-item",
        source_id,
        pdf_path.as_posix(),
        output_directory.as_posix(),
        source_sha256,
        source_byte_size,
        locator,
        extraction_artifact_sha256,
        extraction_manifest_id,
        equation_detection_artifact_sha256,
        equation_detection_result_id,
        TRANSCRIPT_V2_OUTPUT_RELATIVE_PATH.as_posix(),
    )


def _batch_plan_id(
    configuration: CleanTranscriptV2Configuration,
    extraction_low_text_threshold: int,
    items: tuple[TranscriptV2BatchItem, ...],
) -> str:
    return stable_id(
        "transcript-v2-batch-plan",
        TRANSCRIPT_V2_BATCH_PLAN_CONTRACT_ID,
        TRANSCRIPT_V2_BATCH_PLAN_CONTRACT_VERSION,
        TRANSCRIPT_V2_BATCH_PLAN_SCHEMA_VERSION,
        CLEAN_TRANSCRIPT_V2_CONTRACT_ID,
        CLEAN_TRANSCRIPT_V2_CONTRACT_VERSION,
        CLEAN_TRANSCRIPT_V2_ARTIFACT_GENERATION,
        CLEAN_TRANSCRIPT_V2_PROCESSOR_VERSION,
        configuration.configuration_digest,
        extraction_low_text_threshold,
        tuple(item.item_id for item in items),
    )


class TranscriptV2BatchError(ValueError):
    """Base error for transcript-v2 batch planning and execution."""


class TranscriptV2BatchPublicationError(RuntimeError):
    """Raised when an immutable transcript-v2 set cannot be published."""


def _require_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise TranscriptV2BatchError(f"{name} must be a non-empty string")
    if len(value) > _MAX_IDENTITY_LENGTH:
        raise TranscriptV2BatchError(f"{name} exceeds the string limit")
    return value


def _require_sha256(value: object, name: str) -> str:
    digest = _require_text(value, name)
    if len(digest) != _SHA256_LENGTH or digest != digest.lower():
        raise TranscriptV2BatchError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    try:
        int(digest, 16)
    except ValueError as error:
        raise TranscriptV2BatchError(
            f"{name} must be a lowercase SHA-256 digest"
        ) from error
    return digest


def _relative_path(value: object, name: str) -> PurePosixPath:
    text = _require_text(value, name)
    path = PurePosixPath(text)
    if (
        path.is_absolute()
        or not path.parts
        or ".." in path.parts
        or any(part in {"", "."} for part in path.parts)
        or path.as_posix() != text
    ):
        raise TranscriptV2BatchError(f"{name} must be a safe relative path")
    return path


@dataclass(frozen=True)
class TranscriptV2BatchItem:
    item_id: str
    source_id: str
    pdf_path: PurePosixPath
    output_directory: PurePosixPath
    source_sha256: str
    source_byte_size: int
    locator: str | None
    extraction_artifact_sha256: str
    extraction_manifest_id: str
    equation_detection_artifact_sha256: str
    equation_detection_result_id: str

    @classmethod
    def create(
        cls,
        *,
        source_id: str,
        pdf_path: PurePosixPath,
        output_directory: PurePosixPath,
        source_sha256: str,
        source_byte_size: int,
        locator: str | None,
        extraction_artifact_sha256: str,
        extraction_manifest_id: str,
        equation_detection_artifact_sha256: str,
        equation_detection_result_id: str,
    ) -> TranscriptV2BatchItem:
        return cls(
            item_id=_batch_item_id(
                source_id=source_id,
                pdf_path=pdf_path,
                output_directory=output_directory,
                source_sha256=source_sha256,
                source_byte_size=source_byte_size,
                locator=locator,
                extraction_artifact_sha256=extraction_artifact_sha256,
                extraction_manifest_id=extraction_manifest_id,
                equation_detection_artifact_sha256=(
                    equation_detection_artifact_sha256
                ),
                equation_detection_result_id=equation_detection_result_id,
            ),
            source_id=source_id,
            pdf_path=pdf_path,
            output_directory=output_directory,
            source_sha256=source_sha256,
            source_byte_size=source_byte_size,
            locator=locator,
            extraction_artifact_sha256=extraction_artifact_sha256,
            extraction_manifest_id=extraction_manifest_id,
            equation_detection_artifact_sha256=(
                equation_detection_artifact_sha256
            ),
            equation_detection_result_id=equation_detection_result_id,
        )

    def __post_init__(self) -> None:
        _require_text(self.source_id, "source_id")
        if not isinstance(self.pdf_path, PurePosixPath):
            raise TranscriptV2BatchError("pdf_path must be a portable path")
        if not isinstance(self.output_directory, PurePosixPath):
            raise TranscriptV2BatchError(
                "output_directory must be a portable path"
            )
        _relative_path(self.pdf_path.as_posix(), "pdf_path")
        _relative_path(
            self.output_directory.as_posix(), "output_directory"
        )
        if self.pdf_path.suffix.lower() != ".pdf":
            raise TranscriptV2BatchError("pdf_path must name a PDF")
        _require_sha256(self.source_sha256, "source_sha256")
        if (
            isinstance(self.source_byte_size, bool)
            or not isinstance(self.source_byte_size, int)
            or self.source_byte_size <= 0
        ):
            raise TranscriptV2BatchError(
                "source_byte_size must be a positive integer"
            )
        if self.locator is not None:
            _require_text(self.locator, "locator")
        _require_sha256(
            self.extraction_artifact_sha256,
            "extraction_artifact_sha256",
        )
        _require_text(self.extraction_manifest_id, "extraction_manifest_id")
        _require_sha256(
            self.equation_detection_artifact_sha256,
            "equation_detection_artifact_sha256",
        )
        _require_text(
            self.equation_detection_result_id,
            "equation_detection_result_id",
        )
        expected = _batch_item_id(
            source_id=self.source_id,
            pdf_path=self.pdf_path,
            output_directory=self.output_directory,
            source_sha256=self.source_sha256,
            source_byte_size=self.source_byte_size,
            locator=self.locator,
            extraction_artifact_sha256=self.extraction_artifact_sha256,
            extraction_manifest_id=self.extraction_manifest_id,
            equation_detection_artifact_sha256=(
                self.equation_detection_artifact_sha256
            ),
            equation_detection_result_id=self.equation_detection_result_id,
        )
        if self.item_id != expected:
            raise TranscriptV2BatchError("batch item identity is inconsistent")

    def to_pdf_batch_item(self) -> PdfBatchItem:
        return PdfBatchItem(
            source_id=self.source_id,
            pdf_path=self.pdf_path,
            output_directory=self.output_directory,
            sha256=self.source_sha256,
            byte_size=self.source_byte_size,
            locator=self.locator,
        )


@dataclass(frozen=True)
class TranscriptV2BatchPlan:
    plan_id: str
    configuration: CleanTranscriptV2Configuration
    extraction_low_text_threshold: int
    items: tuple[TranscriptV2BatchItem, ...]
    contract_id: str = TRANSCRIPT_V2_BATCH_PLAN_CONTRACT_ID
    contract_version: str = TRANSCRIPT_V2_BATCH_PLAN_CONTRACT_VERSION
    schema_version: int = TRANSCRIPT_V2_BATCH_PLAN_SCHEMA_VERSION
    clean_transcript_contract_id: str = CLEAN_TRANSCRIPT_V2_CONTRACT_ID
    clean_transcript_contract_version: str = (
        CLEAN_TRANSCRIPT_V2_CONTRACT_VERSION
    )
    artifact_generation: int = CLEAN_TRANSCRIPT_V2_ARTIFACT_GENERATION
    processor_version: str = CLEAN_TRANSCRIPT_V2_PROCESSOR_VERSION

    @classmethod
    def create(
        cls,
        *,
        configuration: CleanTranscriptV2Configuration,
        extraction_low_text_threshold: int,
        items: tuple[TranscriptV2BatchItem, ...],
    ) -> TranscriptV2BatchPlan:
        plan_id = _batch_plan_id(
            configuration,
            extraction_low_text_threshold,
            items,
        )
        return cls(
            plan_id=plan_id,
            configuration=configuration,
            extraction_low_text_threshold=extraction_low_text_threshold,
            items=items,
        )

    def __post_init__(self) -> None:
        if (
            self.contract_id != TRANSCRIPT_V2_BATCH_PLAN_CONTRACT_ID
            or self.contract_version
            != TRANSCRIPT_V2_BATCH_PLAN_CONTRACT_VERSION
            or self.schema_version
            != TRANSCRIPT_V2_BATCH_PLAN_SCHEMA_VERSION
            or self.clean_transcript_contract_id
            != CLEAN_TRANSCRIPT_V2_CONTRACT_ID
            or self.clean_transcript_contract_version
            != CLEAN_TRANSCRIPT_V2_CONTRACT_VERSION
            or self.artifact_generation
            != CLEAN_TRANSCRIPT_V2_ARTIFACT_GENERATION
            or self.processor_version != CLEAN_TRANSCRIPT_V2_PROCESSOR_VERSION
        ):
            raise TranscriptV2BatchError(
                "unsupported transcript-v2 batch plan contract"
            )
        if not isinstance(self.configuration, CleanTranscriptV2Configuration):
            raise TranscriptV2BatchError(
                "batch plan configuration is unsupported"
            )
        if (
            isinstance(self.extraction_low_text_threshold, bool)
            or not isinstance(self.extraction_low_text_threshold, int)
            or self.extraction_low_text_threshold < 0
        ):
            raise TranscriptV2BatchError(
                "extraction_low_text_threshold must be non-negative"
            )
        if not isinstance(self.items, tuple) or not self.items:
            raise TranscriptV2BatchError(
                "batch plan must contain an item tuple"
            )
        if len(self.items) > _MAX_ITEMS:
            raise TranscriptV2BatchError("batch plan exceeds the item limit")
        if any(
            not isinstance(item, TranscriptV2BatchItem) for item in self.items
        ):
            raise TranscriptV2BatchError(
                "batch plan contains an unsupported item"
            )
        for name, values in (
            ("item_id", tuple(item.item_id for item in self.items)),
            ("source_id", tuple(item.source_id for item in self.items)),
            (
                "pdf_path",
                tuple(item.pdf_path.as_posix() for item in self.items),
            ),
            (
                "output_directory",
                tuple(
                    item.output_directory.as_posix() for item in self.items
                ),
            ),
        ):
            if len(values) != len(set(values)):
                raise TranscriptV2BatchError(
                    f"batch plan contains duplicate {name} values"
                )
        expected = _batch_plan_id(
            self.configuration,
            self.extraction_low_text_threshold,
            self.items,
        )
        if self.plan_id != expected:
            raise TranscriptV2BatchError("batch plan identity is inconsistent")

    def to_json(self) -> str:
        value = {
            "artifact_generation": self.artifact_generation,
            "clean_transcript_contract_id": (
                self.clean_transcript_contract_id
            ),
            "clean_transcript_contract_version": (
                self.clean_transcript_contract_version
            ),
            "configuration": _configuration_dict(self.configuration),
            "contract_id": self.contract_id,
            "contract_version": self.contract_version,
            "extraction_low_text_threshold": (
                self.extraction_low_text_threshold
            ),
            "items": [_item_dict(item) for item in self.items],
            "plan_id": self.plan_id,
            "processor_version": self.processor_version,
            "schema_version": self.schema_version,
        }
        return json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n"

    @classmethod
    def from_json(cls, text: str) -> TranscriptV2BatchPlan:
        if len(text.encode("utf-8")) > _MAX_PLAN_BYTES:
            raise TranscriptV2BatchError("batch plan exceeds the size limit")
        data = _strict_json_object(text)
        expected = {
            "artifact_generation",
            "clean_transcript_contract_id",
            "clean_transcript_contract_version",
            "configuration",
            "contract_id",
            "contract_version",
            "extraction_low_text_threshold",
            "items",
            "plan_id",
            "processor_version",
            "schema_version",
        }
        if set(data) != expected:
            raise TranscriptV2BatchError(
                "batch plan fields do not match the contract"
            )
        raw_items = data["items"]
        if not isinstance(raw_items, list):
            raise TranscriptV2BatchError("batch plan items must be an array")
        configuration = _configuration_from_dict(data["configuration"])
        items = tuple(_item_from_dict(value) for value in raw_items)
        return cls(
            plan_id=_require_text(data["plan_id"], "plan_id"),
            configuration=configuration,
            extraction_low_text_threshold=_require_int(
                data["extraction_low_text_threshold"],
                "extraction_low_text_threshold",
            ),
            items=items,
            contract_id=_require_text(data["contract_id"], "contract_id"),
            contract_version=_require_text(
                data["contract_version"], "contract_version"
            ),
            schema_version=_require_int(
                data["schema_version"], "schema_version"
            ),
            clean_transcript_contract_id=_require_text(
                data["clean_transcript_contract_id"],
                "clean_transcript_contract_id",
            ),
            clean_transcript_contract_version=_require_text(
                data["clean_transcript_contract_version"],
                "clean_transcript_contract_version",
            ),
            artifact_generation=_require_int(
                data["artifact_generation"], "artifact_generation"
            ),
            processor_version=_require_text(
                data["processor_version"], "processor_version"
            ),
        )


@dataclass(frozen=True)
class ResolvedTranscriptV2BatchItem:
    plan_item: TranscriptV2BatchItem
    source: _ResolvedItem
    target: Path
    existing: bool


def build_transcript_v2_batch_plan(
    source_plan: PdfBatchPlan,
    *,
    source_root: Path,
    ingestion_root: Path,
    configuration: CleanTranscriptV2Configuration | None = None,
    extraction_low_text_threshold: int = 40,
) -> TranscriptV2BatchPlan:
    """Bind exact predecessor artifact identities into a durable plan."""
    _reject_symlinked_item_paths(
        source_plan,
        source_root=source_root,
        ingestion_root=ingestion_root,
    )
    resolved = _resolve_items(
        source_plan,
        source_root=source_root,
        ingestion_root=ingestion_root,
    )
    if not all(item.existing for item in resolved):
        raise TranscriptV2BatchError(
            "equation detection artifacts must exist before v2 planning"
        )
    items: list[TranscriptV2BatchItem] = []
    for source in resolved:
        extraction = _read_json_artifact(source.extraction_artifact)
        detection_bytes = _read_artifact(source.detection_artifact)
        detection = _strict_json_object(detection_bytes.decode("utf-8"))
        manifest_id = _nested_text(
            extraction, ("manifest", "manifest_id"), "extraction manifest_id"
        )
        result_id = _nested_text(
            detection, ("result_id",), "equation detection result_id"
        )
        _verify_detection_source(detection, source.item)
        items.append(
            TranscriptV2BatchItem.create(
                source_id=source.item.source_id,
                pdf_path=source.item.pdf_path,
                output_directory=source.item.output_directory,
                source_sha256=source.item.sha256,
                source_byte_size=source.item.byte_size,
                locator=source.item.locator,
                extraction_artifact_sha256=(
                    source.extraction_artifact_sha256
                ),
                extraction_manifest_id=manifest_id,
                equation_detection_artifact_sha256=hashlib.sha256(
                    detection_bytes
                ).hexdigest(),
                equation_detection_result_id=result_id,
            )
        )
    return TranscriptV2BatchPlan.create(
        configuration=configuration or CleanTranscriptV2Configuration(),
        extraction_low_text_threshold=extraction_low_text_threshold,
        items=tuple(items),
    )


def resolve_transcript_v2_batch_plan(
    plan: TranscriptV2BatchPlan,
    *,
    source_root: Path,
    ingestion_root: Path,
) -> tuple[ResolvedTranscriptV2BatchItem, ...]:
    pdf_plan = PdfBatchPlan(
        schema_version=1,
        items=tuple(item.to_pdf_batch_item() for item in plan.items),
    )
    _reject_symlinked_item_paths(
        pdf_plan,
        source_root=source_root,
        ingestion_root=ingestion_root,
    )
    resolved = _resolve_items(
        pdf_plan,
        source_root=source_root,
        ingestion_root=ingestion_root,
    )
    results: list[ResolvedTranscriptV2BatchItem] = []
    for plan_item, source in zip(plan.items, resolved, strict=True):
        if not source.existing:
            raise TranscriptV2BatchError(
                "equation detection artifacts must exist before v2 execution"
            )
        if (
            source.extraction_artifact_sha256
            != plan_item.extraction_artifact_sha256
        ):
            raise TranscriptV2BatchError(
                "raw extraction artifact differs from the durable plan"
            )
        extraction = _read_json_artifact(source.extraction_artifact)
        if _nested_text(
            extraction, ("manifest", "manifest_id"), "extraction manifest_id"
        ) != plan_item.extraction_manifest_id:
            raise TranscriptV2BatchError(
                "raw extraction identity differs from the durable plan"
            )
        detection_bytes = _read_artifact(source.detection_artifact)
        if hashlib.sha256(detection_bytes).hexdigest() != (
            plan_item.equation_detection_artifact_sha256
        ):
            raise TranscriptV2BatchError(
                "equation detection artifact differs from the durable plan"
            )
        detection = _strict_json_object(detection_bytes.decode("utf-8"))
        if _nested_text(
            detection, ("result_id",), "equation detection result_id"
        ) != plan_item.equation_detection_result_id:
            raise TranscriptV2BatchError(
                "equation detection identity differs from the durable plan"
            )
        _verify_detection_source(detection, source.item)
        target = source.ingestion_directory / Path(
            TRANSCRIPT_V2_OUTPUT_RELATIVE_PATH
        )
        existing = _inspect_target(target)
        results.append(
            ResolvedTranscriptV2BatchItem(
                plan_item=plan_item,
                source=source,
                target=target,
                existing=existing,
            )
        )
    return tuple(results)


def execute_transcript_v2_batch_item(
    resolved: ResolvedTranscriptV2BatchItem,
    *,
    plan: TranscriptV2BatchPlan,
    cache_root: Path | None,
) -> dict[str, object]:
    source = resolved.source
    _require_unchanged_paths(resolved)
    payload, extraction = extract_pdf_evidence(
        source.pdf,
        source_id=source.item.source_id,
        cache_root=cache_root,
        locator=source.item.locator or source.item.pdf_path.as_posix(),
        low_text_threshold=plan.extraction_low_text_threshold,
        expected_source_sha256=source.item.sha256,
        expected_source_byte_size=source.item.byte_size,
    )
    extraction_bytes = _read_artifact(source.extraction_artifact)
    if hashlib.sha256(extraction_bytes).hexdigest() != (
        resolved.plan_item.extraction_artifact_sha256
    ):
        raise TranscriptV2BatchError(
            "raw extraction artifact changed after preflight"
        )
    existing_extraction = _strict_json_object(
        extraction_bytes.decode("utf-8")
    )
    replayed_extraction = contract_dict(extraction)
    if existing_extraction.get("document") != replayed_extraction["document"]:
        raise TranscriptV2BatchError(
            "raw extraction document changed after preflight"
        )

    document = extraction.document
    layouts = DeterministicLayoutProcessor().analyze(document)
    structure = DeterministicArticleStructureAnalyzer().analyze(document)
    equations = DeterministicEquationCandidateDetector().detect_with_layout(
        document,
        BytesIO(payload),
        layouts,
    )
    equation_text = serialize_contract(equations) + "\n"
    if equation_text.encode("utf-8") != _read_artifact(
        source.detection_artifact
    ):
        raise TranscriptV2BatchError(
            "equation detection differs from transcript-v2 replay"
        )
    if equations.result_id != resolved.plan_item.equation_detection_result_id:
        raise TranscriptV2BatchError(
            "equation detection identity differs from transcript-v2 plan"
        )
    table_detection = DeterministicTableCandidateDetector().detect_with_layout(
        document,
        BytesIO(payload),
        layouts,
    )
    tables = DeterministicTableStructureReconstructor().reconstruct(
        table_detection
    )
    figures = DeterministicFigureCandidateDetector().detect_with_layout(
        document,
        BytesIO(payload),
        layouts,
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
    clean = DeterministicCleanTranscriptV2Projector(
        plan.configuration
    ).project(transcription, layouts)
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
            clean_transcript_v2_artifacts=(clean,),
        )
    )
    audit.require_valid()

    clean_json = serialize_contract(clean) + "\n"
    audit_json = serialize_contract(audit) + "\n"
    counts = {
        "clean_blocks": len(clean.blocks),
        "clean_exclusions": len(clean.exclusions),
        "clean_pages": len(clean.pages),
        "dehyphenation_decisions": len(clean.dehyphenation_decisions),
        "equation_candidates": len(equations.candidates),
        "page_number_classifications": len(
            clean.page_number_classifications
        ),
        "private_use_glyph_findings": len(
            clean.private_use_glyph_findings
        ),
        "publisher_front_matter_classifications": len(
            clean.publisher_front_matter
        ),
        "source_blocks": sum(len(page.blocks) for page in document.pages),
        "source_pages": len(document.pages),
        "transcription_items": len(transcription.items),
    }
    manifest_json, manifest = _manifest_text(
        plan=plan,
        item=resolved.plan_item,
        extraction_manifest_id=extraction.manifest.manifest_id,
        layout_result_ids=tuple(layout.result_id for layout in layouts),
        transcription_result_id=transcription.result_id,
        clean_artifact_id=clean.artifact_id,
        clean_artifact_sha256=_sha256_text(clean_json),
        clean_text_sha256=clean.text_sha256,
        audit_report_id=audit.report_id,
        audit_artifact_sha256=_sha256_text(audit_json),
        counts=counts,
    )
    files = {
        "audit.json": audit_json,
        "clean.json": clean_json,
        "clean.txt": clean.text,
        "manifest.json": manifest_json,
    }
    action = "unchanged" if resolved.existing else "created"
    if resolved.existing:
        _verify_existing_set(resolved.target, files)
    else:
        _publish_directory(resolved.target, files)
    return {
        "action": action,
        "audit_report_id": audit.report_id,
        "audit_status": audit.status.value,
        "clean_transcript_artifact_id": clean.artifact_id,
        "clean_text_sha256": clean.text_sha256,
        "counts": counts,
        "manifest_id": manifest["manifest_id"],
        "output_directory": resolved.plan_item.output_directory.as_posix(),
        "source_id": resolved.plan_item.source_id,
    }


def load_durable_plan(path: Path) -> TranscriptV2BatchPlan:
    """Load one bounded, non-symlinked durable execution plan."""
    source = path.expanduser().absolute()
    if source.is_symlink() or not source.is_file():
        raise TranscriptV2BatchError(
            "durable plan must be a safe regular file"
        )
    if source.stat().st_size > _MAX_PLAN_BYTES:
        raise TranscriptV2BatchError("batch plan exceeds the size limit")
    try:
        text = source.read_bytes().decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise TranscriptV2BatchError(
            "durable plan must be valid UTF-8"
        ) from error
    return TranscriptV2BatchPlan.from_json(text)


def publish_durable_plan(path: Path, plan: TranscriptV2BatchPlan) -> str:
    """Publish a plan immutably; return created or unchanged."""
    text = plan.to_json()
    content = text.encode("utf-8")
    if len(content) > _MAX_PLAN_BYTES:
        raise TranscriptV2BatchPublicationError(
            "durable plan exceeds the size limit"
        )
    target = path.expanduser().absolute()
    _require_safe_existing_parents(target.parent)
    _create_private_directories(target.parent)
    _require_safe_existing_parents(target.parent)
    if os.path.lexists(target):
        if target.is_symlink() or not target.is_file():
            raise TranscriptV2BatchPublicationError(
                "durable plan destination is not a safe regular file"
            )
        if target.read_bytes() == content:
            return "unchanged"
        raise TranscriptV2BatchPublicationError(
            "refusing to overwrite a different durable plan"
        )
    temporary: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target.parent,
        )
        temporary = Path(temporary_name)
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, target, follow_symlinks=False)
        _fsync_directory(target.parent)
    except FileExistsError as error:
        raise TranscriptV2BatchPublicationError(
            "durable plan destination appeared during publication"
        ) from error
    except OSError as error:
        raise TranscriptV2BatchPublicationError(
            f"could not publish durable plan: {error}"
        ) from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return "created"


def _configuration_dict(
    configuration: CleanTranscriptV2Configuration,
) -> dict[str, object]:
    return {
        "accepted_hyphenated_forms": list(
            configuration.accepted_hyphenated_forms
        ),
        "accepted_joined_forms": list(configuration.accepted_joined_forms),
        "bottom_margin_fraction": configuration.bottom_margin_fraction,
        "configuration_version": configuration.configuration_version,
        "excluded_publisher_front_matter": [
            item.value for item in configuration.excluded_publisher_front_matter
        ],
        "minimum_page_sequence_length": (
            configuration.minimum_page_sequence_length
        ),
        "minimum_repeated_margin_pages": (
            configuration.minimum_repeated_margin_pages
        ),
        "page_number_horizontal_tolerance_fraction": (
            configuration.page_number_horizontal_tolerance_fraction
        ),
        "repeated_margin_page_fraction": (
            configuration.repeated_margin_page_fraction
        ),
        "top_margin_fraction": configuration.top_margin_fraction,
    }


def _configuration_from_dict(value: object) -> CleanTranscriptV2Configuration:
    if not isinstance(value, dict):
        raise TranscriptV2BatchError("configuration must be an object")
    expected = set(_configuration_dict(CleanTranscriptV2Configuration()))
    if set(value) != expected:
        raise TranscriptV2BatchError(
            "configuration fields do not match the contract"
        )
    joined = _string_tuple(value["accepted_joined_forms"], "joined forms")
    hyphenated = _string_tuple(
        value["accepted_hyphenated_forms"], "hyphenated forms"
    )
    excluded_values = _string_tuple(
        value["excluded_publisher_front_matter"],
        "excluded publisher front matter",
    )
    try:
        excluded = tuple(
            PublisherFrontMatterKind(item) for item in excluded_values
        )
    except ValueError as error:
        raise TranscriptV2BatchError(
            "excluded publisher-front-matter kind is unsupported"
        ) from error
    return CleanTranscriptV2Configuration(
        top_margin_fraction=_require_number(
            value["top_margin_fraction"], "top_margin_fraction"
        ),
        bottom_margin_fraction=_require_number(
            value["bottom_margin_fraction"], "bottom_margin_fraction"
        ),
        minimum_repeated_margin_pages=_require_int(
            value["minimum_repeated_margin_pages"],
            "minimum_repeated_margin_pages",
        ),
        repeated_margin_page_fraction=_require_number(
            value["repeated_margin_page_fraction"],
            "repeated_margin_page_fraction",
        ),
        minimum_page_sequence_length=_require_int(
            value["minimum_page_sequence_length"],
            "minimum_page_sequence_length",
        ),
        page_number_horizontal_tolerance_fraction=_require_number(
            value["page_number_horizontal_tolerance_fraction"],
            "page_number_horizontal_tolerance_fraction",
        ),
        accepted_joined_forms=joined,
        accepted_hyphenated_forms=hyphenated,
        excluded_publisher_front_matter=excluded,
        configuration_version=_require_text(
            value["configuration_version"], "configuration_version"
        ),
    )


def _item_dict(item: TranscriptV2BatchItem) -> dict[str, object]:
    return {
        "equation_detection_artifact_sha256": (
            item.equation_detection_artifact_sha256
        ),
        "equation_detection_result_id": item.equation_detection_result_id,
        "extraction_artifact_sha256": item.extraction_artifact_sha256,
        "extraction_manifest_id": item.extraction_manifest_id,
        "item_id": item.item_id,
        "locator": item.locator,
        "output_directory": item.output_directory.as_posix(),
        "pdf_path": item.pdf_path.as_posix(),
        "source_byte_size": item.source_byte_size,
        "source_id": item.source_id,
        "source_sha256": item.source_sha256,
    }


def _item_from_dict(value: object) -> TranscriptV2BatchItem:
    if not isinstance(value, dict):
        raise TranscriptV2BatchError("batch item must be an object")
    expected = set(
        _item_dict(
            TranscriptV2BatchItem.create(
                source_id="fixture",
                pdf_path=PurePosixPath("fixture.pdf"),
                output_directory=PurePosixPath("fixture"),
                source_sha256="0" * 64,
                source_byte_size=1,
                locator=None,
                extraction_artifact_sha256="1" * 64,
                extraction_manifest_id="manifest:fixture",
                equation_detection_artifact_sha256="2" * 64,
                equation_detection_result_id="equation:fixture",
            )
        )
    )
    if set(value) != expected:
        raise TranscriptV2BatchError(
            "batch item fields do not match the contract"
        )
    locator = value["locator"]
    if locator is not None:
        locator = _require_text(locator, "locator")
    return TranscriptV2BatchItem(
        item_id=_require_text(value["item_id"], "item_id"),
        source_id=_require_text(value["source_id"], "source_id"),
        pdf_path=_relative_path(value["pdf_path"], "pdf_path"),
        output_directory=_relative_path(
            value["output_directory"], "output_directory"
        ),
        source_sha256=_require_sha256(
            value["source_sha256"], "source_sha256"
        ),
        source_byte_size=_require_int(
            value["source_byte_size"], "source_byte_size"
        ),
        locator=locator,
        extraction_artifact_sha256=_require_sha256(
            value["extraction_artifact_sha256"],
            "extraction_artifact_sha256",
        ),
        extraction_manifest_id=_require_text(
            value["extraction_manifest_id"], "extraction_manifest_id"
        ),
        equation_detection_artifact_sha256=_require_sha256(
            value["equation_detection_artifact_sha256"],
            "equation_detection_artifact_sha256",
        ),
        equation_detection_result_id=_require_text(
            value["equation_detection_result_id"],
            "equation_detection_result_id",
        ),
    )


def _strict_json_object(text: str) -> dict[str, Any]:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise TranscriptV2BatchError(
                    f"JSON contains duplicate member: {key}"
                )
            result[key] = value
        return result

    try:
        value = json.loads(text, object_pairs_hook=pairs)
    except (json.JSONDecodeError, RecursionError) as error:
        raise TranscriptV2BatchError("JSON is malformed") from error
    if not isinstance(value, dict):
        raise TranscriptV2BatchError("JSON root must be an object")
    return value


def _read_artifact(
    path: Path, *, label: str = "predecessor artifact"
) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise TranscriptV2BatchError(f"{label} is missing or unsafe")
    content = path.read_bytes()
    if len(content) > _MAX_ARTIFACT_BYTES:
        raise TranscriptV2BatchError(f"{label} exceeds size limit")
    return content


def _read_json_artifact(path: Path) -> dict[str, Any]:
    content = _read_artifact(path)
    try:
        text = content.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise TranscriptV2BatchError(
            "predecessor artifact is not valid UTF-8"
        ) from error
    return _strict_json_object(text)


def _nested_text(
    value: dict[str, Any], path: tuple[str, ...], name: str
) -> str:
    current: object = value
    for part in path:
        if not isinstance(current, dict) or part not in current:
            raise TranscriptV2BatchError(f"{name} is missing")
        current = current[part]
    return _require_text(current, name)


def _verify_detection_source(
    detection: dict[str, Any], item: PdfBatchItem
) -> None:
    source_id = _nested_text(
        detection,
        ("detection_input", "document", "source", "source_id"),
        "equation detection source_id",
    )
    source_hash = _nested_text(
        detection,
        ("detection_input", "document", "source", "content_hash"),
        "equation detection source hash",
    )
    if source_id != item.source_id or source_hash != item.sha256:
        raise TranscriptV2BatchError(
            "equation detection source differs from the source plan"
        )


def _reject_symlinked_item_paths(
    plan: PdfBatchPlan,
    *,
    source_root: Path,
    ingestion_root: Path,
) -> None:
    roots = (
        (source_root.expanduser().absolute(), "source root"),
        (ingestion_root.expanduser().absolute(), "ingestion root"),
    )
    for root, name in roots:
        if root.is_symlink():
            raise TranscriptV2BatchError(f"{name} cannot be a symlink")
    for item in plan.items:
        for root, relative, name in (
            (source_root, item.pdf_path, "source PDF"),
            (
                ingestion_root,
                item.output_directory,
                "ingestion destination",
            ),
        ):
            current = root.expanduser().absolute()
            for part in relative.parts:
                current /= part
                if current.is_symlink():
                    raise TranscriptV2BatchError(
                        f"{name} cannot traverse a symlink: {relative}"
                    )


def _inspect_target(target: Path) -> bool:
    _require_safe_existing_parents(target.parent)
    if not os.path.lexists(target):
        return False
    if target.is_symlink() or not target.is_dir():
        raise TranscriptV2BatchError(
            "transcript-v2 destination is not a safe directory"
        )
    names = tuple(sorted(path.name for path in target.iterdir()))
    if names != _OUTPUT_NAMES:
        raise TranscriptV2BatchError(
            "transcript-v2 artifact set is incomplete or contains extras"
        )
    for name in _OUTPUT_NAMES:
        path = target / name
        if path.is_symlink() or not path.is_file():
            raise TranscriptV2BatchError(
                "transcript-v2 artifact is not a safe regular file"
            )
    return True


def _require_unchanged_paths(resolved: ResolvedTranscriptV2BatchItem) -> None:
    source = resolved.source
    if source.ingestion_directory.resolve() != source.ingestion_directory:
        raise TranscriptV2BatchError("ingestion path changed after preflight")
    current_existing = _inspect_target(resolved.target)
    if current_existing != resolved.existing:
        raise TranscriptV2BatchError(
            "transcript-v2 destination changed after preflight"
        )


def _manifest_text(
    *,
    plan: TranscriptV2BatchPlan,
    item: TranscriptV2BatchItem,
    extraction_manifest_id: str,
    layout_result_ids: tuple[str, ...],
    transcription_result_id: str,
    clean_artifact_id: str,
    clean_artifact_sha256: str,
    clean_text_sha256: str,
    audit_report_id: str,
    audit_artifact_sha256: str,
    counts: dict[str, int],
) -> tuple[str, dict[str, object]]:
    manifest_id = stable_id(
        "transcript-v2-batch-manifest",
        TRANSCRIPT_V2_BATCH_MANIFEST_SCHEMA_VERSION,
        plan.plan_id,
        item.item_id,
        extraction_manifest_id,
        layout_result_ids,
        transcription_result_id,
        clean_artifact_id,
        clean_artifact_sha256,
        clean_text_sha256,
        audit_report_id,
        audit_artifact_sha256,
        tuple(sorted(counts.items())),
    )
    value: dict[str, object] = {
        "artifact_generation": CLEAN_TRANSCRIPT_V2_ARTIFACT_GENERATION,
        "audit_artifact_sha256": audit_artifact_sha256,
        "audit_report_id": audit_report_id,
        "clean_artifact_id": clean_artifact_id,
        "clean_artifact_sha256": clean_artifact_sha256,
        "clean_text_sha256": clean_text_sha256,
        "configuration_digest": plan.configuration.configuration_digest,
        "contract_id": CLEAN_TRANSCRIPT_V2_CONTRACT_ID,
        "contract_version": CLEAN_TRANSCRIPT_V2_CONTRACT_VERSION,
        "counts": dict(sorted(counts.items())),
        "equation_detection_artifact_sha256": (
            item.equation_detection_artifact_sha256
        ),
        "equation_detection_result_id": item.equation_detection_result_id,
        "extraction_artifact_sha256": item.extraction_artifact_sha256,
        "extraction_manifest_id": extraction_manifest_id,
        "item_id": item.item_id,
        "layout_result_ids": list(layout_result_ids),
        "limitations": [
            "automated_unreviewed",
            "not_human_proofread",
            "not_publication_suitable",
            "not_scientifically_validated",
            "not_semantically_corrected",
        ],
        "manifest_id": manifest_id,
        "output_relative_path": (
            TRANSCRIPT_V2_OUTPUT_RELATIVE_PATH.as_posix()
        ),
        "plan_id": plan.plan_id,
        "processor_version": CLEAN_TRANSCRIPT_V2_PROCESSOR_VERSION,
        "schema_version": TRANSCRIPT_V2_BATCH_MANIFEST_SCHEMA_VERSION,
        "source_byte_size": item.source_byte_size,
        "source_id": item.source_id,
        "source_sha256": item.source_sha256,
        "status": "automated_unreviewed",
        "transcription_result_id": transcription_result_id,
    }
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        value,
    )


def _verify_existing_set(target: Path, files: dict[str, str]) -> None:
    _inspect_target(target)
    for name in _OUTPUT_NAMES:
        actual = _read_artifact(
            target / name,
            label=f"existing transcript-v2 artifact {name}",
        )
        if actual != files[name].encode("utf-8"):
            raise TranscriptV2BatchPublicationError(
                f"existing transcript-v2 artifact differs: {name}"
            )


def _publish_directory(target: Path, files: dict[str, str]) -> None:
    _require_safe_existing_parents(target.parent)
    if os.path.lexists(target):
        raise TranscriptV2BatchPublicationError(
            "refusing to overwrite transcript-v2 artifacts"
        )
    _create_private_directories(target.parent)
    _require_safe_existing_parents(target.parent)
    lock = target.parent / f".{target.name}.publish.lock"
    staging: Path | None = None
    lock_descriptor: int | None = None
    try:
        lock_descriptor = os.open(
            lock,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        staging = Path(
            tempfile.mkdtemp(
                prefix=f".{target.name}.tmp-",
                dir=target.parent,
            )
        )
        os.chmod(staging, 0o700)
        for name in _OUTPUT_NAMES:
            _write_staged_file(staging / name, files[name])
        _fsync_directory(staging)
        if os.path.lexists(target):
            raise TranscriptV2BatchPublicationError(
                "transcript-v2 destination appeared during publication"
            )
        os.rename(staging, target)
        staging = None
        _fsync_directory(target.parent)
    except TranscriptV2BatchPublicationError:
        raise
    except FileExistsError as error:
        raise TranscriptV2BatchPublicationError(
            "another transcript-v2 publication is active"
        ) from error
    except OSError as error:
        raise TranscriptV2BatchPublicationError(
            f"could not publish transcript-v2 artifacts: {error}"
        ) from error
    finally:
        if lock_descriptor is not None:
            os.close(lock_descriptor)
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)
        if lock_descriptor is not None:
            lock.unlink(missing_ok=True)


def _write_staged_file(path: Path, text: str) -> None:
    content = text.encode("utf-8")
    if len(content) > _MAX_ARTIFACT_BYTES:
        raise TranscriptV2BatchPublicationError(
            f"transcript-v2 artifact exceeds size limit: {path.name}"
        )
    descriptor = os.open(
        path,
        os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def _create_private_directories(path: Path) -> None:
    missing: list[Path] = []
    current = path.absolute()
    while not current.exists():
        missing.append(current)
        if current == current.parent:
            break
        current = current.parent
    for directory in reversed(missing):
        try:
            directory.mkdir(mode=0o700)
        except FileExistsError:
            if directory.is_symlink() or not directory.is_dir():
                raise TranscriptV2BatchPublicationError(
                    "artifact parent changed during creation"
                ) from None


def _require_safe_existing_parents(path: Path) -> None:
    current = path.absolute()
    while not current.exists():
        if current == current.parent:
            break
        current = current.parent
    if current.is_symlink() or not current.is_dir():
        raise TranscriptV2BatchPublicationError(
            "artifact parent is not a safe directory"
        )
    if current.resolve() != current:
        raise TranscriptV2BatchPublicationError(
            "artifact parent must not traverse a symlink"
        )


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _require_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TranscriptV2BatchError(f"{name} must be an integer")
    return value


def _require_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TranscriptV2BatchError(f"{name} must be a number")
    return float(value)


def _string_tuple(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise TranscriptV2BatchError(f"{name} must be an array")
    return tuple(_require_text(item, name) for item in value)
