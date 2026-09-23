from __future__ import annotations

import hashlib
import math
import unicodedata
from collections import Counter
from dataclasses import dataclass, fields, is_dataclass
from enum import StrEnum
from typing import Any

from projectkoios.ingestion.base import BaseDerivationAuditValidator
from projectkoios.ingestion.equations import EquationDetectionResult
from projectkoios.ingestion.figures import FigureDetectionResult
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout import PageLayoutResult
from projectkoios.ingestion.models import (
    ExtractedBlock,
    ExtractedDocument,
    ExtractionResult,
    Metadata,
    SourceDocument,
    SourceSpan,
)
from projectkoios.ingestion.ocr.models import OcrResult
from projectkoios.ingestion.pdf.models import RenderedRegion
from projectkoios.ingestion.processing import ProcessingResult
from projectkoios.ingestion.reconciliation import OCRReconciliationResult
from projectkoios.ingestion.structure import StructureAnalysis
from projectkoios.ingestion.table_structure import TableStructureResult
from projectkoios.ingestion.tables import TableDetectionResult
from projectkoios.ingestion.transcript_projection import CleanTranscriptArtifact
from projectkoios.ingestion.transcript_v2 import (
    ClassificationDisposition,
    CleanTranscriptV2Artifact,
    CleanTranscriptV2ExclusionReason,
    PageNumberOutcome,
)
from projectkoios.ingestion.transcription import (
    StructuredTranscriptionResult,
    TranscriptionSourceObjectKind,
)

DERIVATION_AUDIT_CONTRACT_VERSION = "1.0"
DERIVATION_AUDIT_PROCESSOR_VERSION = "2"
DERIVATION_AUDIT_V2_PROCESSOR_VERSION = "3"
_MAX_ARTIFACTS_PER_LAYER = 4_096
_MAX_FINDINGS = 8_192
_MAX_VISITED_OBJECTS = 250_000
_BOX_TOLERANCE = 1e-6


class DerivationAuditLimitError(ValueError):
    """Raised before a derivation audit exceeds a deterministic bound."""


class DerivationAuditError(ValueError):
    """Raised when a caller requires a valid derivation audit."""

    def __init__(self, report: DerivationAuditReport) -> None:
        self.report = report
        super().__init__(
            f"derivation audit failed with {len(report.findings)} finding(s)"
        )


class DerivationAuditStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class DerivationAuditFindingCode(StrEnum):
    SOURCE_CONTENT_MISMATCH = "source_content_mismatch"
    SOURCE_DOCUMENT_MISMATCH = "source_document_mismatch"
    SOURCE_ID_MISMATCH = "source_id_mismatch"
    SOURCE_BLOB_MISMATCH = "source_blob_mismatch"
    SOURCE_HASH_MISMATCH = "source_hash_mismatch"
    PAGE_OUT_OF_RANGE = "page_out_of_range"
    REGION_OUT_OF_RANGE = "region_out_of_range"
    CONTENT_IDENTITY_MISMATCH = "content_identity_mismatch"
    PROCESSOR_IDENTITY_MISSING = "processor_identity_missing"
    CONTRACT_VERSION_MISSING = "contract_version_missing"
    INTRINSIC_CONTRACT_VIOLATION = "intrinsic_contract_violation"
    ORPHAN_OBJECT_REFERENCE = "orphan_object_reference"
    UPSTREAM_ARTIFACT_MISSING = "upstream_artifact_missing"
    UPSTREAM_ARTIFACT_MISMATCH = "upstream_artifact_mismatch"
    DUPLICATE_OBJECT_ID = "duplicate_object_id"


@dataclass(frozen=True)
class DerivationAuditFinding:
    finding_id: str
    code: DerivationAuditFindingCode
    path: str
    message: str
    object_id: str | None = None
    evidence: Metadata = ()
    contract_version: str = DERIVATION_AUDIT_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        code: DerivationAuditFindingCode,
        path: str,
        message: str,
        object_id: str | None = None,
        evidence: Metadata = (),
    ) -> DerivationAuditFinding:
        normalized_evidence = tuple(sorted(evidence))
        finding_id = stable_id(
            "derivation-audit-finding",
            code,
            path,
            object_id,
            normalized_evidence,
        )
        return cls(
            finding_id=finding_id,
            code=code,
            path=path,
            message=message,
            object_id=object_id,
            evidence=normalized_evidence,
        )

    def __post_init__(self) -> None:
        if self.contract_version != DERIVATION_AUDIT_CONTRACT_VERSION:
            raise ValueError("unsupported derivation-audit finding contract")
        if not self.path or not self.message:
            raise ValueError("audit finding path and message must be non-empty")
        if self.evidence != tuple(sorted(self.evidence)):
            raise ValueError("audit finding evidence must be sorted")
        expected = stable_id(
            "derivation-audit-finding",
            self.code,
            self.path,
            self.object_id,
            self.evidence,
        )
        if self.finding_id != expected:
            raise ValueError("audit finding ID is inconsistent")


@dataclass(frozen=True)
class DerivationAuditInput:
    source_content: bytes
    extraction_result: ExtractionResult
    ocr_results: tuple[OcrResult, ...] = ()
    reconciliation_results: tuple[OCRReconciliationResult, ...] = ()
    layout_results: tuple[PageLayoutResult, ...] = ()
    structure_analyses: tuple[StructureAnalysis, ...] = ()
    equation_results: tuple[EquationDetectionResult, ...] = ()
    table_detection_results: tuple[TableDetectionResult, ...] = ()
    table_structure_results: tuple[TableStructureResult, ...] = ()
    figure_results: tuple[FigureDetectionResult, ...] = ()
    processing_results: tuple[ProcessingResult, ...] = ()
    transcription_results: tuple[StructuredTranscriptionResult, ...] = ()
    clean_transcript_artifacts: tuple[CleanTranscriptArtifact, ...] = ()
    contract_version: str = DERIVATION_AUDIT_CONTRACT_VERSION
    clean_transcript_v2_artifacts: tuple[CleanTranscriptV2Artifact, ...] = ()

    def __post_init__(self) -> None:
        if self.contract_version != DERIVATION_AUDIT_CONTRACT_VERSION:
            raise ValueError("unsupported derivation-audit input contract")
        if not isinstance(self.source_content, bytes):
            raise TypeError("source_content must be exact bytes")
        if not isinstance(self.extraction_result, ExtractionResult):
            raise TypeError("extraction_result must be ExtractionResult")
        for name in _LAYER_FIELDS:
            value = getattr(self, name)
            if not isinstance(value, tuple):
                raise TypeError(f"{name} must be a tuple")
            if len(value) > _MAX_ARTIFACTS_PER_LAYER:
                raise DerivationAuditLimitError(
                    f"{name} exceeds {_MAX_ARTIFACTS_PER_LAYER} artifacts"
                )
            expected_type = _LAYER_TYPES[name]
            if any(not isinstance(item, expected_type) for item in value):
                raise TypeError(
                    f"{name} must contain only {expected_type.__name__}"
                )


@dataclass(frozen=True)
class DerivationAuditReport:
    report_id: str
    source_id: str
    source_blob_id: str
    source_content_hash: str
    document_id: str
    audited_artifact_ids: tuple[str, ...]
    audited_layer_counts: Metadata
    findings: tuple[DerivationAuditFinding, ...]
    status: DerivationAuditStatus
    processor_name: str
    processor_version: str
    contract_version: str = DERIVATION_AUDIT_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        source: SourceDocument,
        document_id: str,
        audited_artifact_ids: tuple[str, ...],
        audited_layer_counts: Metadata,
        findings: tuple[DerivationAuditFinding, ...],
        processor_name: str,
        processor_version: str,
    ) -> DerivationAuditReport:
        status = (
            DerivationAuditStatus.PASSED
            if not findings
            else DerivationAuditStatus.FAILED
        )
        report_id = stable_id(
            "derivation-audit-report",
            source.source_id,
            source.blob_id,
            source.content_hash,
            document_id,
            audited_artifact_ids,
            audited_layer_counts,
            tuple(item.finding_id for item in findings),
            status,
            processor_name,
            processor_version,
        )
        return cls(
            report_id=report_id,
            source_id=source.source_id,
            source_blob_id=source.blob_id,
            source_content_hash=source.content_hash,
            document_id=document_id,
            audited_artifact_ids=audited_artifact_ids,
            audited_layer_counts=audited_layer_counts,
            findings=findings,
            status=status,
            processor_name=processor_name,
            processor_version=processor_version,
        )

    @property
    def valid(self) -> bool:
        return self.status is DerivationAuditStatus.PASSED

    def require_valid(self) -> None:
        if not self.valid:
            raise DerivationAuditError(self)

    def __post_init__(self) -> None:
        if self.contract_version != DERIVATION_AUDIT_CONTRACT_VERSION:
            raise ValueError("unsupported derivation-audit report contract")
        if not all(
            (
                self.source_id,
                self.source_blob_id,
                self.source_content_hash,
                self.document_id,
                self.processor_name,
                self.processor_version,
            )
        ):
            raise ValueError("derivation-audit report identity is incomplete")
        if self.audited_layer_counts != tuple(
            sorted(self.audited_layer_counts)
        ):
            raise ValueError("audited layer counts must be sorted")
        expected_status = (
            DerivationAuditStatus.PASSED
            if not self.findings
            else DerivationAuditStatus.FAILED
        )
        if self.status is not expected_status:
            raise ValueError("audit status does not match findings")
        expected = stable_id(
            "derivation-audit-report",
            self.source_id,
            self.source_blob_id,
            self.source_content_hash,
            self.document_id,
            self.audited_artifact_ids,
            self.audited_layer_counts,
            tuple(item.finding_id for item in self.findings),
            self.status,
            self.processor_name,
            self.processor_version,
        )
        if self.report_id != expected:
            raise ValueError("derivation-audit report ID is inconsistent")


_LAYER_TYPES: dict[str, type[object]] = {
    "ocr_results": OcrResult,
    "reconciliation_results": OCRReconciliationResult,
    "layout_results": PageLayoutResult,
    "structure_analyses": StructureAnalysis,
    "equation_results": EquationDetectionResult,
    "table_detection_results": TableDetectionResult,
    "table_structure_results": TableStructureResult,
    "figure_results": FigureDetectionResult,
    "processing_results": ProcessingResult,
    "transcription_results": StructuredTranscriptionResult,
    "clean_transcript_artifacts": CleanTranscriptArtifact,
    "clean_transcript_v2_artifacts": CleanTranscriptV2Artifact,
}
_LAYER_FIELDS = (
    "ocr_results",
    "reconciliation_results",
    "layout_results",
    "structure_analyses",
    "equation_results",
    "table_detection_results",
    "table_structure_results",
    "figure_results",
    "processing_results",
    "transcription_results",
    "clean_transcript_artifacts",
    "clean_transcript_v2_artifacts",
)


@dataclass
class _Registry:
    layouts: dict[str, PageLayoutResult]
    structures: dict[str, StructureAnalysis]
    ocr_results: dict[str, OcrResult]
    equations: dict[str, EquationDetectionResult]
    table_detections: dict[str, TableDetectionResult]
    table_structures: dict[str, TableStructureResult]
    figures: dict[str, FigureDetectionResult]
    processing: dict[str, ProcessingResult]
    transcriptions: dict[str, StructuredTranscriptionResult]
    clean_transcripts: dict[str, CleanTranscriptArtifact]
    clean_transcripts_v2: dict[str, CleanTranscriptV2Artifact]


class DerivationAuditValidator(BaseDerivationAuditValidator):
    """Validate exact transitive provenance without changing any artifact."""

    name = "deterministic-derivation-audit-validator"
    version = DERIVATION_AUDIT_PROCESSOR_VERSION

    def audit(self, audit_input: DerivationAuditInput) -> DerivationAuditReport:
        processor_version = (
            DERIVATION_AUDIT_V2_PROCESSOR_VERSION
            if audit_input.clean_transcript_v2_artifacts
            else self.version
        )
        state = _AuditState(audit_input, self.name, processor_version)
        state.run()
        return state.report()

    def validate(self, audit_input: DerivationAuditInput) -> None:
        self.audit(audit_input).require_valid()


class _AuditState:
    def __init__(
        self,
        audit_input: DerivationAuditInput,
        processor_name: str,
        processor_version: str,
    ) -> None:
        self.audit_input = audit_input
        self.extraction = audit_input.extraction_result
        self.document = self.extraction.document
        self.source = self.document.source
        self.processor_name = processor_name
        self.processor_version = processor_version
        self.pages = {page.page_index: page for page in self.document.pages}
        self.blocks = {
            block.block_id: block
            for page in self.document.pages
            for block in page.blocks
        }
        self.block_pages = {
            block.block_id: page
            for page in self.document.pages
            for block in page.blocks
        }
        self.findings: list[DerivationAuditFinding] = []
        self._finding_keys: set[tuple[object, ...]] = set()
        self._seen_objects: set[int] = set()
        self._visited_count = 0
        self.registry = _Registry(
            layouts=self._index(
                audit_input.layout_results, "result_id", "layout_results"
            ),
            structures=self._index(
                audit_input.structure_analyses,
                "analysis_id",
                "structure_analyses",
            ),
            ocr_results=self._index(
                audit_input.ocr_results, "result_id", "ocr_results"
            ),
            equations=self._index(
                audit_input.equation_results,
                "result_id",
                "equation_results",
            ),
            table_detections=self._index(
                audit_input.table_detection_results,
                "result_id",
                "table_detection_results",
            ),
            table_structures=self._index(
                audit_input.table_structure_results,
                "result_id",
                "table_structure_results",
            ),
            figures=self._index(
                audit_input.figure_results, "result_id", "figure_results"
            ),
            processing=self._index(
                audit_input.processing_results,
                "result_id",
                "processing_results",
            ),
            transcriptions=self._index(
                audit_input.transcription_results,
                "result_id",
                "transcription_results",
            ),
            clean_transcripts=self._index(
                audit_input.clean_transcript_artifacts,
                "artifact_id",
                "clean_transcript_artifacts",
            ),
            clean_transcripts_v2=self._index(
                audit_input.clean_transcript_v2_artifacts,
                "artifact_id",
                "clean_transcript_v2_artifacts",
            ),
        )

    def run(self) -> None:
        self._audit_source_content()
        self._audit_extraction()
        self._audit_layout_references()
        self._audit_registered_upstreams()
        self._audit_structure_references()
        self._audit_ocr_references()
        self._audit_reconciliation_references()
        self._audit_equation_references()
        self._audit_table_references()
        self._audit_figure_references()
        self._audit_processing_references()
        self._audit_transcription_references()
        self._audit_clean_transcript_references()
        self._audit_clean_transcript_v2_references()
        self._walk(self.extraction, "extraction_result")
        for layer_name in _LAYER_FIELDS:
            for index, artifact in enumerate(
                getattr(self.audit_input, layer_name)
            ):
                self._walk(artifact, f"{layer_name}[{index}]")

    def report(self) -> DerivationAuditReport:
        artifact_ids = [
            self.extraction.manifest.manifest_id,
            self.document.document_id,
        ]
        for name in _LAYER_FIELDS:
            artifact_ids.extend(
                _artifact_id(item) for item in getattr(self.audit_input, name)
            )
        layer_counts = tuple(
            sorted(
                (
                    ("extraction_result", "1"),
                    *(
                        (name, str(len(getattr(self.audit_input, name))))
                        for name in _LAYER_FIELDS
                        if name != "clean_transcript_v2_artifacts"
                        or self.audit_input.clean_transcript_v2_artifacts
                    ),
                )
            )
        )
        return DerivationAuditReport.create(
            source=self.source,
            document_id=self.document.document_id,
            audited_artifact_ids=tuple(artifact_ids),
            audited_layer_counts=layer_counts,
            findings=tuple(self.findings),
            processor_name=self.processor_name,
            processor_version=self.processor_version,
        )

    def _index(
        self, values: tuple[Any, ...], field_name: str, path: str
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for index, value in enumerate(values):
            identity = getattr(value, field_name)
            if (
                identity is None
                or not isinstance(identity, str)
                or not identity
            ):
                self._add(
                    DerivationAuditFindingCode.INTRINSIC_CONTRACT_VIOLATION,
                    f"{path}[{index}].{field_name}",
                    "artifact identity is missing",
                    _object_id(value),
                )
                continue
            if identity in result:
                self._add(
                    DerivationAuditFindingCode.DUPLICATE_OBJECT_ID,
                    f"{path}[{index}].{field_name}",
                    "artifact identity is duplicated in the audit input",
                    identity,
                )
                continue
            result[identity] = value
        return result

    def _audit_source_content(self) -> None:
        content = self.audit_input.source_content
        digest = hashlib.sha256(content).hexdigest()
        if (
            digest != self.source.content_hash
            or len(content) != self.source.byte_length
        ):
            self._add(
                DerivationAuditFindingCode.SOURCE_CONTENT_MISMATCH,
                "source_content",
                "source bytes do not match the extraction source identity",
                self.source.source_id,
                (
                    ("actual_byte_length", str(len(content))),
                    ("actual_sha256", digest),
                    ("expected_byte_length", str(self.source.byte_length)),
                    ("expected_sha256", self.source.content_hash),
                ),
            )

    def _audit_extraction(self) -> None:
        manifest = self.extraction.manifest
        expected_objects = {self.document.document_id, *self.blocks}
        missing = expected_objects - set(manifest.object_ids)
        for object_id in sorted(missing):
            self._add(
                DerivationAuditFindingCode.ORPHAN_OBJECT_REFERENCE,
                "extraction_result.manifest.object_ids",
                "raw extraction object is absent from the manifest",
                object_id,
            )
        if len(self.blocks) != sum(
            len(page.blocks) for page in self.document.pages
        ):
            self._add(
                DerivationAuditFindingCode.DUPLICATE_OBJECT_ID,
                "extraction_result.document.pages",
                "raw block IDs are not globally unique",
                self.document.document_id,
            )

    def _audit_layout_references(self) -> None:
        for result_index, result in enumerate(self.audit_input.layout_results):
            prefix = f"layout_results[{result_index}]"
            page = self.pages.get(result.page_index)
            if page is None:
                continue
            expected_ids = tuple(block.block_id for block in page.blocks)
            if result.raw_block_ids != expected_ids:
                self._add(
                    DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                    f"{prefix}.raw_block_ids",
                    "layout raw block order differs from the root page",
                    result.result_id,
                )
            root_blocks = {block.block_id: block for block in page.blocks}
            for reference_index, reference in enumerate(result.raw_blocks):
                block = root_blocks.get(reference.block_id)
                if block is None:
                    continue
                if (
                    reference.kind != block.kind
                    or reference.source_spans != block.source_spans
                ):
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                        f"{prefix}.raw_blocks[{reference_index}]",
                        "layout block reference differs from its root block",
                        reference.block_id,
                    )

    def _audit_registered_upstreams(self) -> None:
        for index, result in enumerate(self.audit_input.reconciliation_results):
            prefix = f"reconciliation_results[{index}].reconciliation_input"
            self._require_registered(
                result.reconciliation_input.ocr_result,
                self.registry.ocr_results,
                result.reconciliation_input.ocr_result.result_id,
                f"{prefix}.ocr_result",
            )
            native_page = result.reconciliation_input.native_page
            if native_page is not None:
                root_page = self.pages.get(native_page.page_index)
                if root_page != native_page:
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                        f"{prefix}.native_page",
                        "OCR reconciliation native page differs from "
                        "the root page",
                    )
            layout = result.reconciliation_input.layout_result
            if layout is not None:
                self._require_registered(
                    layout,
                    self.registry.layouts,
                    layout.result_id,
                    f"{prefix}.layout_result",
                )
        for name, results in (
            ("equation_results", self.audit_input.equation_results),
            (
                "table_detection_results",
                self.audit_input.table_detection_results,
            ),
            ("figure_results", self.audit_input.figure_results),
        ):
            for index, detection_result in enumerate(results):
                detection_value: Any = detection_result
                detection_input = detection_value.detection_input
                self._require_root_document(
                    detection_input.document,
                    f"{name}[{index}].detection_input.document",
                )
                for layout_index, layout in enumerate(detection_input.layouts):
                    self._require_registered(
                        layout,
                        self.registry.layouts,
                        layout.result_id,
                        f"{name}[{index}].detection_input.layouts[{layout_index}]",
                    )
        for index, table_structure_result in enumerate(
            self.audit_input.table_structure_results
        ):
            detection = table_structure_result.structure_input.detection_result
            self._require_registered(
                detection,
                self.registry.table_detections,
                detection.result_id,
                f"table_structure_results[{index}].structure_input.detection_result",
            )
        for index, transcription_result in enumerate(
            self.audit_input.transcription_results
        ):
            transcription_input = transcription_result.transcription_input
            prefix = f"transcription_results[{index}].transcription_input"
            self._require_root_document(
                transcription_input.document, f"{prefix}.document"
            )
            dependencies = (
                (
                    transcription_input.structure_analysis,
                    self.registry.structures,
                    transcription_input.structure_analysis.analysis_id,
                    "structure_analysis",
                ),
                (
                    transcription_input.equation_detection_result,
                    self.registry.equations,
                    transcription_input.equation_detection_result.result_id,
                    "equation_detection_result",
                ),
                (
                    transcription_input.table_structure_result,
                    self.registry.table_structures,
                    transcription_input.table_structure_result.result_id,
                    "table_structure_result",
                ),
                (
                    transcription_input.figure_detection_result,
                    self.registry.figures,
                    transcription_input.figure_detection_result.result_id,
                    "figure_detection_result",
                ),
            )
            for artifact, registry, identity, suffix in dependencies:
                if identity is None:
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISSING,
                        f"{prefix}.{suffix}",
                        "transcription dependency has no artifact identity",
                    )
                else:
                    self._require_registered(
                        artifact,
                        registry,
                        identity,
                        f"{prefix}.{suffix}",
                    )
        for index, clean_artifact in enumerate(
            self.audit_input.clean_transcript_artifacts
        ):
            prefix = f"clean_transcript_artifacts[{index}]"
            if (
                clean_artifact.transcription_result_id
                not in self.registry.transcriptions
            ):
                self._add(
                    DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISSING,
                    f"{prefix}.transcription_result_id",
                    "clean transcript references an unregistered transcription",
                    clean_artifact.transcription_result_id,
                )
            for layout_index, layout_id in enumerate(
                clean_artifact.layout_result_ids
            ):
                if layout_id not in self.registry.layouts:
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISSING,
                        f"{prefix}.layout_result_ids[{layout_index}]",
                        "clean transcript references an unregistered layout",
                        layout_id,
                    )
        for index, v2_artifact in enumerate(
            self.audit_input.clean_transcript_v2_artifacts
        ):
            prefix = f"clean_transcript_v2_artifacts[{index}]"
            if (
                v2_artifact.transcription_result_id
                not in self.registry.transcriptions
            ):
                self._add(
                    DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISSING,
                    f"{prefix}.transcription_result_id",
                    "transcript v2 references an unregistered transcription",
                    v2_artifact.transcription_result_id,
                )
            for layout_index, layout_id in enumerate(
                v2_artifact.layout_result_ids
            ):
                if layout_id not in self.registry.layouts:
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISSING,
                        f"{prefix}.layout_result_ids[{layout_index}]",
                        "transcript v2 references an unregistered layout",
                        layout_id,
                    )

    def _audit_structure_references(self) -> None:
        for index, analysis in enumerate(self.audit_input.structure_analyses):
            prefix = f"structure_analyses[{index}]"
            for layout_id in analysis.layout_result_ids:
                if layout_id not in self.registry.layouts:
                    self._orphan(f"{prefix}.layout_result_ids", layout_id)
            node_ids = {node.node_id for node in analysis.nodes}
            for node_index, node in enumerate(analysis.nodes):
                node_path = f"{prefix}.nodes[{node_index}]"
                if (
                    node.parent_id is not None
                    and node.parent_id not in node_ids
                ):
                    self._orphan(f"{node_path}.parent_id", node.parent_id)
                for child_id in node.child_ids:
                    if child_id not in node_ids:
                        self._orphan(f"{node_path}.child_ids", child_id)

    def _audit_ocr_references(self) -> None:
        for result_index, result in enumerate(self.audit_input.ocr_results):
            prefix = f"ocr_results[{result_index}]"
            selections = {
                selection.selection_id: selection
                for selection in result.request.selections
            }
            for selection_index, selection_result in enumerate(
                result.selection_results
            ):
                path = f"{prefix}.selection_results[{selection_index}]"
                selection = selections.get(selection_result.selection_id)
                if selection is None:
                    self._orphan(
                        f"{path}.selection_id", selection_result.selection_id
                    )
                    continue
                if selection_result.image_id != selection.image.image_id:
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                        f"{path}.image_id",
                        "OCR output image does not match its request selection",
                        selection_result.image_id,
                    )

    def _audit_reconciliation_references(self) -> None:
        for result_index, result in enumerate(
            self.audit_input.reconciliation_results
        ):
            prefix = f"reconciliation_results[{result_index}]"
            native_evidence_ids = {
                item.evidence_id for item in result.native_stream
            }
            native_segment_ids = {
                item.segment_id for item in result.native_segments
            }
            ocr_line_ids = {item.line_id for item in result.ocr_stream}
            for segment_index, segment in enumerate(result.native_segments):
                if segment.block_evidence_id not in native_evidence_ids:
                    self._orphan(
                        f"{prefix}.native_segments[{segment_index}].block_evidence_id",
                        segment.block_evidence_id,
                    )
            for match_index, match in enumerate(result.matches):
                if match.native_segment_id not in native_segment_ids:
                    self._orphan(
                        f"{prefix}.matches[{match_index}].native_segment_id",
                        match.native_segment_id,
                    )
                if match.ocr_line_id not in ocr_line_ids:
                    self._orphan(
                        f"{prefix}.matches[{match_index}].ocr_line_id",
                        match.ocr_line_id,
                    )
            for item_index, item in enumerate(result.proposed_merged_stream):
                path = f"{prefix}.proposed_merged_stream[{item_index}]"
                if (
                    item.native_segment_id is not None
                    and item.native_segment_id not in native_segment_ids
                ):
                    self._orphan(
                        f"{path}.native_segment_id", item.native_segment_id
                    )
                if (
                    item.ocr_line_id is not None
                    and item.ocr_line_id not in ocr_line_ids
                ):
                    self._orphan(f"{path}.ocr_line_id", item.ocr_line_id)

    def _audit_equation_references(self) -> None:
        for result_index, result in enumerate(
            self.audit_input.equation_results
        ):
            for candidate_index, candidate in enumerate(result.candidates):
                prefix = (
                    f"equation_results[{result_index}].candidates"
                    f"[{candidate_index}]"
                )
                for context_name in ("preceding_context", "following_context"):
                    context = getattr(candidate, context_name)
                    if (
                        context is not None
                        and context.block_id not in self.blocks
                    ):
                        self._orphan(
                            f"{prefix}.{context_name}.block_id",
                            context.block_id,
                        )

    def _audit_table_references(self) -> None:
        candidate_by_id = {
            candidate.candidate_id: candidate
            for result in self.audit_input.table_detection_results
            for candidate in result.candidates
        }
        region_ids = {
            region.region_evidence_id
            for candidate in candidate_by_id.values()
            for region in candidate.regions
        }
        rendered_region_ids = {
            region.rendered_region.region_id
            for candidate in candidate_by_id.values()
            for region in candidate.regions
        }
        association_ids = {
            association.association_id
            for candidate in candidate_by_id.values()
            for association in candidate.associations
        }
        for result_index, result in enumerate(
            self.audit_input.table_structure_results
        ):
            for structure_index, structure in enumerate(result.structures):
                prefix = (
                    f"table_structure_results[{result_index}].structures"
                    f"[{structure_index}]"
                )
                if structure.candidate_id not in candidate_by_id:
                    self._orphan(
                        f"{prefix}.candidate_id", structure.candidate_id
                    )
                for association_id in structure.association_ids:
                    if association_id not in association_ids:
                        self._orphan(
                            f"{prefix}.association_ids", association_id
                        )
                row_ids = {row.row_id for row in structure.rows}
                column_indexes = {
                    column.column_index for column in structure.columns
                }
                for column_index, column in enumerate(structure.columns):
                    for region_id in column.source_region_ids:
                        if region_id not in region_ids:
                            self._orphan(
                                f"{prefix}.columns[{column_index}].source_region_ids",
                                region_id,
                            )
                for row_index, row in enumerate(structure.rows):
                    if row.region_id not in region_ids:
                        self._orphan(
                            f"{prefix}.rows[{row_index}].region_id",
                            row.region_id,
                        )
                for cell_index, cell in enumerate(structure.cells):
                    if cell.row_id not in row_ids:
                        self._orphan(
                            f"{prefix}.cells[{cell_index}].row_id",
                            cell.row_id,
                        )
                    if cell.column_index not in column_indexes:
                        self._orphan(
                            f"{prefix}.cells[{cell_index}].column_index",
                            str(cell.column_index),
                        )
                    for region_id in cell.rendered_region_ids:
                        if region_id not in rendered_region_ids:
                            self._orphan(
                                f"{prefix}.cells[{cell_index}].rendered_region_ids",
                                region_id,
                            )
                for continuation_index, continuation in enumerate(
                    structure.continuations
                ):
                    path = f"{prefix}.continuations[{continuation_index}]"
                    for name in ("previous_region_id", "current_region_id"):
                        value = getattr(continuation, name)
                        if value not in region_ids:
                            self._orphan(f"{path}.{name}", value)
                    if continuation.association_id not in association_ids:
                        self._orphan(
                            f"{path}.association_id",
                            continuation.association_id,
                        )

    def _audit_figure_references(self) -> None:
        for result_index, result in enumerate(self.audit_input.figure_results):
            artifact_ids = {
                artifact.artifact_id
                for evidence in result.detection_input.page_evidence
                for artifact in evidence.embedded_artifacts
            }
            drawing_ids = {
                drawing.drawing_id
                for evidence in result.detection_input.page_evidence
                for drawing in evidence.drawings
            }
            for candidate_index, candidate in enumerate(result.candidates):
                prefix = (
                    f"figure_results[{result_index}].candidates"
                    f"[{candidate_index}]"
                )
                component_ids = {
                    component.component_id for component in candidate.components
                }
                for component_index, component in enumerate(
                    candidate.components
                ):
                    path = f"{prefix}.components[{component_index}]"
                    if (
                        component.embedded_artifact_id is not None
                        and component.embedded_artifact_id not in artifact_ids
                    ):
                        self._orphan(
                            f"{path}.embedded_artifact_id",
                            component.embedded_artifact_id,
                        )
                    for drawing_id in component.drawing_evidence_ids:
                        if drawing_id not in drawing_ids:
                            self._orphan(
                                f"{path}.drawing_evidence_ids", drawing_id
                            )
                for association_index, association in enumerate(
                    candidate.associations
                ):
                    if (
                        association.component_id is not None
                        and association.component_id not in component_ids
                    ):
                        self._orphan(
                            f"{prefix}.associations[{association_index}].component_id",
                            association.component_id,
                        )

    def _audit_processing_references(self) -> None:
        for result_index, result in enumerate(
            self.audit_input.processing_results
        ):
            prefix = f"processing_results[{result_index}]"
            selection_by_id = {
                selection.selection_id: selection
                for selection in result.request.selections
            }
            work_item_by_id = {
                work_item.work_item_id: work_item
                for work_item in result.request.work_items
            }
            for selection_index, selection in enumerate(
                result.request.selections
            ):
                self._require_root_document(
                    selection.document,
                    f"{prefix}.request.selections[{selection_index}].document",
                )
                if selection.structure_analysis is not None:
                    identity = selection.structure_analysis.analysis_id
                    if identity is None:
                        self._add(
                            DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISSING,
                            f"{prefix}.request.selections[{selection_index}].structure_analysis",
                            "processing selection structure has no identity",
                        )
                    else:
                        self._require_registered(
                            selection.structure_analysis,
                            self.registry.structures,
                            identity,
                            f"{prefix}.request.selections[{selection_index}].structure_analysis",
                        )
            for work_index, work_item in enumerate(result.request.work_items):
                path = f"{prefix}.request.work_items[{work_index}]"
                if work_item.source != self.source:
                    self._add(
                        DerivationAuditFindingCode.SOURCE_DOCUMENT_MISMATCH,
                        f"{path}.source",
                        "processing work item source differs from root source",
                        work_item.work_item_id,
                    )
                for page_index, full_page in enumerate(work_item.full_pages):
                    root_page = self.pages.get(full_page.page_index)
                    if root_page != full_page:
                        self._add(
                            DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                            f"{path}.full_pages[{page_index}]",
                            "processing work item page differs from "
                            "the root page",
                            work_item.work_item_id,
                        )
            for selection_result_index, selection_result in enumerate(
                result.selection_results
            ):
                path = f"{prefix}.selection_results[{selection_result_index}]"
                if selection_result.selection_id not in selection_by_id:
                    self._orphan(
                        f"{path}.selection_id", selection_result.selection_id
                    )
                registered_work_item = work_item_by_id.get(
                    selection_result.work_item.work_item_id
                )
                if registered_work_item is None:
                    self._orphan(
                        f"{path}.work_item.work_item_id",
                        selection_result.work_item.work_item_id,
                    )
                elif registered_work_item != selection_result.work_item:
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                        f"{path}.work_item",
                        "processing selection result embeds different "
                        "work item evidence",
                        selection_result.work_item.work_item_id,
                    )
                allowed_input_ids = set(
                    selection_result.work_item.input_object_ids
                )
                for attempt_index, attempt in enumerate(
                    selection_result.attempts
                ):
                    invocation = attempt.invocation
                    for artifact_index, artifact in enumerate(
                        invocation.artifacts
                    ):
                        for object_id in artifact.input_object_ids:
                            if object_id not in allowed_input_ids:
                                self._orphan(
                                    f"{path}.attempts[{attempt_index}].invocation.artifacts"
                                    f"[{artifact_index}].input_object_ids",
                                    object_id,
                                )

    def _audit_transcription_references(self) -> None:
        structure_ids = {
            node.node_id
            for analysis in self.audit_input.structure_analyses
            for node in analysis.nodes
        }
        equation_ids = {
            candidate.candidate_id
            for result in self.audit_input.equation_results
            for candidate in result.candidates
        }
        table_structure_ids = {
            structure.structure_id
            for result in self.audit_input.table_structure_results
            for structure in result.structures
        }
        figure_ids = {
            candidate.candidate_id
            for result in self.audit_input.figure_results
            for candidate in result.candidates
        }
        page_anchor_ids = {
            stable_id(
                "transcription-page-anchor",
                self.source.source_id,
                self.source.blob_id,
                page.page_index,
            )
            for page in self.document.pages
        }
        expected = {
            TranscriptionSourceObjectKind.PAGE: page_anchor_ids,
            TranscriptionSourceObjectKind.RAW_BLOCK: set(self.blocks),
            TranscriptionSourceObjectKind.STRUCTURE_NODE: structure_ids,
            TranscriptionSourceObjectKind.EQUATION_CANDIDATE: equation_ids,
            TranscriptionSourceObjectKind.TABLE_STRUCTURE: table_structure_ids,
            TranscriptionSourceObjectKind.FIGURE_CANDIDATE: figure_ids,
        }
        all_source_objects = set().union(*expected.values())
        for result_index, result in enumerate(
            self.audit_input.transcription_results
        ):
            item_ids = {item.item_id for item in result.items}
            for item_index, item in enumerate(result.items):
                if (
                    item.source_object_id
                    not in expected[item.source_object_kind]
                ):
                    self._orphan(
                        f"transcription_results[{result_index}].items"
                        f"[{item_index}].source_object_id",
                        item.source_object_id,
                    )
            for omission_index, omission in enumerate(result.omissions):
                prefix = (
                    f"transcription_results[{result_index}].omissions"
                    f"[{omission_index}]"
                )
                if omission.omitted_object_id not in all_source_objects:
                    self._orphan(
                        f"{prefix}.omitted_object_id",
                        omission.omitted_object_id,
                    )
                for item_id in omission.represented_by_item_ids:
                    if item_id not in item_ids:
                        self._orphan(
                            f"{prefix}.represented_by_item_ids", item_id
                        )

    def _audit_clean_transcript_references(self) -> None:
        root_page_indexes = tuple(
            page.page_index for page in self.document.pages
        )
        eligible_root_ids = tuple(
            block.block_id
            for page in self.document.pages
            for block in page.blocks
            if block.kind == "text" and block.text is not None
        )
        for artifact_index, artifact in enumerate(
            self.audit_input.clean_transcript_artifacts
        ):
            prefix = f"clean_transcript_artifacts[{artifact_index}]"
            if artifact.document_id != self.document.document_id:
                self._add(
                    DerivationAuditFindingCode.SOURCE_DOCUMENT_MISMATCH,
                    f"{prefix}.document_id",
                    "clean transcript document differs from the root document",
                    artifact.artifact_id,
                )

            record_id_counts = Counter(
                record.record_id for record in artifact.blocks
            )
            exclusion_id_counts = Counter(
                exclusion.exclusion_id for exclusion in artifact.exclusions
            )
            for record_id, count in sorted(record_id_counts.items()):
                if count > 1:
                    self._add(
                        DerivationAuditFindingCode.DUPLICATE_OBJECT_ID,
                        f"{prefix}.blocks",
                        "clean transcript block record ID is duplicated",
                        record_id,
                    )
            for exclusion_id, count in sorted(exclusion_id_counts.items()):
                if count > 1:
                    self._add(
                        DerivationAuditFindingCode.DUPLICATE_OBJECT_ID,
                        f"{prefix}.exclusions",
                        "clean transcript exclusion ID is duplicated",
                        exclusion_id,
                    )

            block_records = {
                record.record_id: record for record in artifact.blocks
            }
            included_by_block = {
                record.block_id: record for record in artifact.blocks
            }
            excluded_by_block = {
                exclusion.block_id: exclusion
                for exclusion in artifact.exclusions
            }
            coverage_counts = Counter(
                (
                    *(record.block_id for record in artifact.blocks),
                    *(item.block_id for item in artifact.exclusions),
                )
            )
            included_counts = Counter(
                record.block_id for record in artifact.blocks
            )
            excluded_counts = Counter(
                item.block_id for item in artifact.exclusions
            )

            for record_index, record in enumerate(artifact.blocks):
                path = f"{prefix}.blocks[{record_index}]"
                root = self.blocks.get(record.block_id)
                root_page = self.block_pages.get(record.block_id)
                if root is None or root_page is None:
                    self._orphan(f"{path}.block_id", record.block_id)
                elif (
                    root.kind != "text"
                    or root.text is None
                    or root.text != record.raw_text
                    or root.source_spans != record.source_spans
                    or root_page.page_index != record.page_index
                    or root_page.printed_page_label != record.printed_page_label
                ):
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                        path,
                        "clean transcript block differs from its root block",
                        record.record_id,
                    )
            for exclusion_index, exclusion in enumerate(artifact.exclusions):
                path = f"{prefix}.exclusions[{exclusion_index}]"
                root = self.blocks.get(exclusion.block_id)
                root_page = self.block_pages.get(exclusion.block_id)
                if root is None or root_page is None:
                    self._orphan(f"{path}.block_id", exclusion.block_id)
                elif (
                    root.kind != "text"
                    or root.text is None
                    or root.text != exclusion.raw_text
                    or root.source_spans != exclusion.source_spans
                    or root_page.page_index != exclusion.page_index
                    or root_page.printed_page_label
                    != exclusion.printed_page_label
                ):
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                        path,
                        "clean transcript exclusion differs from its "
                        "root block",
                        exclusion.exclusion_id,
                    )

            for block_id in eligible_root_ids:
                count = coverage_counts[block_id]
                if count == 0:
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISSING,
                        f"{prefix}.blocks_and_exclusions",
                        "eligible root text block is absent from the clean "
                        "transcript partition",
                        block_id,
                    )
                elif count > 1:
                    self._add(
                        DerivationAuditFindingCode.DUPLICATE_OBJECT_ID,
                        f"{prefix}.blocks_and_exclusions",
                        "eligible root text block occurs more than once in "
                        "the clean transcript partition",
                        block_id,
                        (
                            ("excluded_count", str(excluded_counts[block_id])),
                            ("included_count", str(included_counts[block_id])),
                        ),
                    )

            actual_page_indexes = tuple(
                page.page_index for page in artifact.pages
            )
            if actual_page_indexes != root_page_indexes:
                self._add(
                    DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                    f"{prefix}.pages",
                    "clean transcript pages do not exactly cover root pages "
                    "in source order",
                    artifact.artifact_id,
                )

            clean_layouts = tuple(
                self.registry.layouts[layout_id]
                for layout_id in artifact.layout_result_ids
                if layout_id in self.registry.layouts
            )
            layout_page_indexes = tuple(
                layout.page_index for layout in clean_layouts
            )
            if (
                len(clean_layouts) == len(artifact.layout_result_ids)
                and layout_page_indexes != root_page_indexes
            ):
                self._add(
                    DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                    f"{prefix}.layout_result_ids",
                    "clean transcript layouts do not exactly cover root "
                    "pages in source order",
                    artifact.artifact_id,
                )
            layout_by_page = {
                layout.page_index: layout for layout in clean_layouts
            }

            actual_order = tuple(
                record.order_index for record in artifact.blocks
            )
            if actual_order != tuple(range(len(artifact.blocks))):
                self._add(
                    DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                    f"{prefix}.blocks",
                    "clean transcript block order indices are not contiguous "
                    "in retained order",
                    artifact.artifact_id,
                )

            listed_record_counts: Counter[str] = Counter()
            expected_global_record_ids: list[str] = []
            expected_exclusion_ids: list[str] = []
            for page_position, root_page in enumerate(self.document.pages):
                page = (
                    artifact.pages[page_position]
                    if page_position < len(artifact.pages)
                    else None
                )
                if page is not None:
                    page_path = f"{prefix}.pages[{page_position}]"
                    if (
                        page.page_index != root_page.page_index
                        or page.printed_page_label
                        != root_page.printed_page_label
                    ):
                        self._add(
                            DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                            page_path,
                            "clean transcript page differs from its root page",
                            page.page_id,
                        )
                    for record_id in page.block_record_ids:
                        listed_record_counts[record_id] += 1
                        page_record = block_records.get(record_id)
                        if page_record is None:
                            self._orphan(
                                f"{page_path}.block_record_ids", record_id
                            )
                        elif page_record.page_index != page.page_index:
                            self._add(
                                DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                                f"{page_path}.block_record_ids",
                                "clean transcript page references another "
                                "page's block",
                                record_id,
                            )

                layout = layout_by_page.get(root_page.page_index)
                block_by_id = {
                    block.block_id: block for block in root_page.blocks
                }
                text_ids = tuple(
                    block.block_id
                    for block in root_page.blocks
                    if block.kind == "text" and block.text is not None
                )
                ordered_ids = (
                    tuple(
                        block_id
                        for block_id in layout.proposed_order
                        if block_id in block_by_id
                        and block_by_id[block_id].kind == "text"
                        and block_by_id[block_id].text is not None
                    )
                    if layout is not None
                    else text_ids
                )
                fallback_ids = tuple(
                    block_id
                    for block_id in text_ids
                    if block_id not in ordered_ids
                )
                root_order = (*ordered_ids, *fallback_ids)
                expected_page_record_ids = tuple(
                    included_by_block[block_id].record_id
                    for block_id in root_order
                    if block_id in included_by_block
                )
                expected_global_record_ids.extend(expected_page_record_ids)
                expected_exclusion_ids.extend(
                    excluded_by_block[block_id].exclusion_id
                    for block_id in root_order
                    if block_id in excluded_by_block
                )
                if (
                    page is not None
                    and page.block_record_ids != expected_page_record_ids
                ):
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                        f"{prefix}.pages[{page_position}].block_record_ids",
                        "clean transcript page block membership or order "
                        "differs from its layout",
                        page.page_id,
                    )

            for record in artifact.blocks:
                listed_count = listed_record_counts[record.record_id]
                if listed_count == 0:
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISSING,
                        f"{prefix}.pages.block_record_ids",
                        "clean transcript block is absent from page membership",
                        record.record_id,
                    )
                elif listed_count > 1:
                    self._add(
                        DerivationAuditFindingCode.DUPLICATE_OBJECT_ID,
                        f"{prefix}.pages.block_record_ids",
                        "clean transcript block occurs in page membership "
                        "more than once",
                        record.record_id,
                    )

            if tuple(record.record_id for record in artifact.blocks) != tuple(
                expected_global_record_ids
            ):
                self._add(
                    DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                    f"{prefix}.blocks",
                    "clean transcript blocks are not retained in exact "
                    "page and layout order",
                    artifact.artifact_id,
                )
            if tuple(
                item.exclusion_id for item in artifact.exclusions
            ) != tuple(expected_exclusion_ids):
                self._add(
                    DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                    f"{prefix}.exclusions",
                    "clean transcript exclusions are not retained in exact "
                    "page and layout order",
                    artifact.artifact_id,
                )

            expected_text = (
                "\n\n".join(page.text for page in artifact.pages) + "\n"
            )
            if artifact.text != expected_text:
                self._add(
                    DerivationAuditFindingCode.CONTENT_IDENTITY_MISMATCH,
                    f"{prefix}.text",
                    "clean transcript text differs from its page projections",
                    artifact.artifact_id,
                )

    def _audit_clean_transcript_v2_references(self) -> None:
        root_page_indexes = tuple(
            page.page_index for page in self.document.pages
        )
        eligible_root_ids = tuple(
            block.block_id
            for page in self.document.pages
            for block in page.blocks
            if block.kind == "text" and block.text is not None
        )
        for artifact_index, artifact in enumerate(
            self.audit_input.clean_transcript_v2_artifacts
        ):
            prefix = f"clean_transcript_v2_artifacts[{artifact_index}]"
            if (
                artifact.document_id != self.document.document_id
                or artifact.source_id != self.source.source_id
                or artifact.source_blob_id != self.source.blob_id
                or artifact.source_content_hash != self.source.content_hash
            ):
                self._add(
                    DerivationAuditFindingCode.SOURCE_DOCUMENT_MISMATCH,
                    prefix,
                    "transcript v2 differs from the root source document",
                    artifact.artifact_id,
                )
            included_by_block = {
                record.block_id: record for record in artifact.blocks
            }
            excluded_by_block = {
                exclusion.block_id: exclusion
                for exclusion in artifact.exclusions
            }
            coverage_counts = Counter(
                (
                    *(record.block_id for record in artifact.blocks),
                    *(item.block_id for item in artifact.exclusions),
                )
            )
            for block_id in eligible_root_ids:
                count = coverage_counts[block_id]
                if count == 0:
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISSING,
                        f"{prefix}.blocks_and_exclusions",
                        "eligible root block is absent from transcript v2",
                        block_id,
                    )
                elif count > 1:
                    self._add(
                        DerivationAuditFindingCode.DUPLICATE_OBJECT_ID,
                        f"{prefix}.blocks_and_exclusions",
                        "root block occurs more than once in transcript v2",
                        block_id,
                    )
            for record_index, record in enumerate(artifact.blocks):
                path = f"{prefix}.blocks[{record_index}]"
                root = self.blocks.get(record.block_id)
                root_page = self.block_pages.get(record.block_id)
                if root is None or root_page is None:
                    self._orphan(f"{path}.block_id", record.block_id)
                elif (
                    root.kind != "text"
                    or root.text is None
                    or root.text != record.raw_text
                    or root.source_spans != record.source_spans
                    or root_page.page_index != record.page_index
                    or root_page.printed_page_label != record.printed_page_label
                ):
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                        path,
                        "transcript-v2 block differs from its root block",
                        record.record_id,
                    )
            for exclusion_index, exclusion in enumerate(artifact.exclusions):
                path = f"{prefix}.exclusions[{exclusion_index}]"
                root = self.blocks.get(exclusion.block_id)
                root_page = self.block_pages.get(exclusion.block_id)
                if root is None or root_page is None:
                    self._orphan(f"{path}.block_id", exclusion.block_id)
                elif (
                    root.kind != "text"
                    or root.text is None
                    or root.text != exclusion.raw_text
                    or root.source_spans != exclusion.source_spans
                    or root_page.page_index != exclusion.page_index
                    or root_page.printed_page_label
                    != exclusion.printed_page_label
                ):
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                        path,
                        "transcript-v2 exclusion differs from its root block",
                        exclusion.exclusion_id,
                    )
            page_classification_by_id = {
                item.classification_id: item
                for item in artifact.page_number_classifications
            }
            publisher_by_id = {
                item.classification_id: item
                for item in artifact.publisher_front_matter
            }
            exclusions_by_decision = {
                item.decision_id: item
                for item in artifact.exclusions
                if item.decision_id is not None
            }
            for decision_index, decision in enumerate(
                artifact.dehyphenation_decisions
            ):
                path = f"{prefix}.dehyphenation_decisions[{decision_index}]"
                root = self.blocks.get(decision.block_id)
                root_page = self.block_pages.get(decision.block_id)
                if root is None or root_page is None or root.text is None:
                    self._orphan(f"{path}.block_id", decision.block_id)
                elif (
                    root.source_spans != decision.source_spans
                    or root_page.page_index != decision.page_index
                    or root_page.printed_page_label
                    != decision.printed_page_label
                    or decision.end_offset > len(root.text)
                    or root.text[decision.start_offset : decision.end_offset]
                    != decision.raw_fragment
                ):
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                        path,
                        "dehyphenation decision differs from source evidence",
                        decision.decision_id,
                    )
            for classification_index, page_classification in enumerate(
                artifact.page_number_classifications
            ):
                path = (
                    f"{prefix}.page_number_classifications"
                    f"[{classification_index}]"
                )
                root = self.blocks.get(page_classification.block_id)
                root_page = self.block_pages.get(page_classification.block_id)
                boxes = (
                    tuple(
                        span.bounding_box
                        for span in root.source_spans
                        if span.bounding_box is not None
                    )
                    if root is not None
                    else ()
                )
                expected_box = (
                    (
                        min(box[0] for box in boxes),
                        min(box[1] for box in boxes),
                        max(box[2] for box in boxes),
                        max(box[3] for box in boxes),
                    )
                    if boxes
                    else None
                )
                if root is None or root_page is None or root.text is None:
                    self._orphan(
                        f"{path}.block_id", page_classification.block_id
                    )
                elif (
                    root.text != page_classification.raw_text
                    or root.source_spans != page_classification.source_spans
                    or root_page.page_index != page_classification.page_index
                    or root_page.printed_page_label
                    != page_classification.printed_page_label
                    or page_classification.bounding_box != expected_box
                ):
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                        path,
                        "page-number decision differs from source evidence",
                        page_classification.classification_id,
                    )
                page_exclusion = exclusions_by_decision.get(
                    page_classification.classification_id
                )
                if (
                    page_classification.outcome is PageNumberOutcome.PAGE_NUMBER
                    and (
                        page_exclusion is None
                        or page_exclusion.reason
                        is not CleanTranscriptV2ExclusionReason.PAGE_NUMBER
                    )
                ):
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISSING,
                        path,
                        "page-number decision lacks its typed exclusion",
                        page_classification.classification_id,
                    )
                if (
                    page_classification.outcome
                    is not PageNumberOutcome.PAGE_NUMBER
                    and page_exclusion is not None
                    and page_exclusion.reason
                    is CleanTranscriptV2ExclusionReason.PAGE_NUMBER
                ):
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                        path,
                        "non-page-number evidence was excluded as a page "
                        "number",
                        page_classification.classification_id,
                    )
            for classification_index, publisher_classification in enumerate(
                artifact.publisher_front_matter
            ):
                path = (
                    f"{prefix}.publisher_front_matter[{classification_index}]"
                )
                root = self.blocks.get(publisher_classification.block_id)
                root_page = self.block_pages.get(
                    publisher_classification.block_id
                )
                if root is None or root_page is None:
                    self._orphan(
                        f"{path}.block_id",
                        publisher_classification.block_id,
                    )
                elif (
                    root.source_spans != publisher_classification.source_spans
                    or root_page.page_index
                    != publisher_classification.page_index
                ):
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                        path,
                        "publisher classification differs from source evidence",
                        publisher_classification.classification_id,
                    )
                publisher_exclusion = exclusions_by_decision.get(
                    publisher_classification.classification_id
                )
                if (
                    publisher_classification.disposition
                    is ClassificationDisposition.EXCLUDED
                    and (
                        publisher_exclusion is None
                        or publisher_exclusion.reason
                        is not (
                            CleanTranscriptV2ExclusionReason.PUBLISHER_FRONT_MATTER
                        )
                    )
                ):
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISSING,
                        path,
                        "publisher exclusion lacks its classification",
                        publisher_classification.classification_id,
                    )
            for finding_index, finding in enumerate(
                artifact.private_use_glyph_findings
            ):
                path = f"{prefix}.private_use_glyph_findings[{finding_index}]"
                root = self.blocks.get(finding.block_id)
                root_page = self.block_pages.get(finding.block_id)
                if root is None or root_page is None or root.text is None:
                    self._orphan(f"{path}.block_id", finding.block_id)
                elif (
                    root.source_spans != finding.source_spans
                    or root_page.page_index != finding.page_index
                    or root_page.printed_page_label
                    != finding.printed_page_label
                    or finding.character_offset >= len(root.text)
                    or root.text[finding.character_offset]
                    != finding.raw_character
                ):
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                        path,
                        "private-use finding differs from source evidence",
                        finding.finding_id,
                    )
            expected_private_use = {
                (block.block_id, offset, character)
                for page in self.document.pages
                for block in page.blocks
                if block.kind == "text" and block.text is not None
                for offset, character in enumerate(block.text)
                if unicodedata.category(character) == "Co"
            }
            actual_private_use = {
                (item.block_id, item.character_offset, item.raw_character)
                for item in artifact.private_use_glyph_findings
            }
            if actual_private_use != expected_private_use:
                self._add(
                    DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                    f"{prefix}.private_use_glyph_findings",
                    "private-use findings do not exactly cover source glyphs",
                    artifact.artifact_id,
                )
            actual_page_indexes = tuple(
                page.page_index for page in artifact.pages
            )
            if actual_page_indexes != root_page_indexes:
                self._add(
                    DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                    f"{prefix}.pages",
                    "transcript-v2 pages do not exactly cover root pages",
                    artifact.artifact_id,
                )
            layouts = tuple(
                self.registry.layouts[layout_id]
                for layout_id in artifact.layout_result_ids
                if layout_id in self.registry.layouts
            )
            layout_by_page = {layout.page_index: layout for layout in layouts}
            expected_record_ids: list[str] = []
            expected_exclusion_ids: list[str] = []
            for page_index, root_page in enumerate(self.document.pages):
                block_by_id = {
                    block.block_id: block for block in root_page.blocks
                }
                text_ids = tuple(
                    block.block_id
                    for block in root_page.blocks
                    if block.kind == "text" and block.text is not None
                )
                layout = layout_by_page.get(root_page.page_index)
                ordered_ids = (
                    tuple(
                        block_id
                        for block_id in layout.proposed_order
                        if block_id in block_by_id
                        and block_by_id[block_id].kind == "text"
                        and block_by_id[block_id].text is not None
                    )
                    if layout is not None
                    else text_ids
                )
                root_order = (
                    *ordered_ids,
                    *(
                        block_id
                        for block_id in text_ids
                        if block_id not in ordered_ids
                    ),
                )
                page_record_ids = tuple(
                    included_by_block[block_id].record_id
                    for block_id in root_order
                    if block_id in included_by_block
                )
                expected_record_ids.extend(page_record_ids)
                expected_exclusion_ids.extend(
                    excluded_by_block[block_id].exclusion_id
                    for block_id in root_order
                    if block_id in excluded_by_block
                )
                if (
                    page_index >= len(artifact.pages)
                    or artifact.pages[page_index].block_record_ids
                    != page_record_ids
                    or artifact.pages[page_index].printed_page_label
                    != root_page.printed_page_label
                ):
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                        f"{prefix}.pages[{page_index}]",
                        "transcript-v2 page membership differs from layout",
                        artifact.artifact_id,
                    )
            if tuple(item.record_id for item in artifact.blocks) != tuple(
                expected_record_ids
            ):
                self._add(
                    DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                    f"{prefix}.blocks",
                    "transcript-v2 blocks are not in exact layout order",
                    artifact.artifact_id,
                )
            if tuple(
                item.exclusion_id for item in artifact.exclusions
            ) != tuple(expected_exclusion_ids):
                self._add(
                    DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                    f"{prefix}.exclusions",
                    "transcript-v2 exclusions are not in exact layout order",
                    artifact.artifact_id,
                )
            if tuple(item.order_index for item in artifact.blocks) != tuple(
                range(len(artifact.blocks))
            ):
                self._add(
                    DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                    f"{prefix}.blocks",
                    "transcript-v2 retained order is not contiguous",
                    artifact.artifact_id,
                )
            expected_text = (
                "\n\n".join(page.text for page in artifact.pages) + "\n"
            )
            if artifact.text != expected_text:
                self._add(
                    DerivationAuditFindingCode.CONTENT_IDENTITY_MISMATCH,
                    f"{prefix}.text",
                    "transcript-v2 text differs from page projections",
                    artifact.artifact_id,
                )
            for record in artifact.blocks:
                if record.page_number_classification_id is not None and (
                    record.page_number_classification_id
                    not in page_classification_by_id
                ):
                    self._orphan(
                        f"{prefix}.blocks.page_number_classification_id",
                        record.page_number_classification_id,
                    )
                if record.publisher_classification_id is not None and (
                    record.publisher_classification_id not in publisher_by_id
                ):
                    self._orphan(
                        f"{prefix}.blocks.publisher_classification_id",
                        record.publisher_classification_id,
                    )

    def _walk(self, value: object, path: str) -> None:
        if isinstance(
            value, (str, bytes, int, float, bool, type(None), StrEnum)
        ):
            return
        if isinstance(value, tuple):
            for index, item in enumerate(value):
                self._walk(item, f"{path}[{index}]")
            return
        if not is_dataclass(value):
            return
        identity = id(value)
        if identity in self._seen_objects:
            return
        self._seen_objects.add(identity)
        self._visited_count += 1
        if self._visited_count > _MAX_VISITED_OBJECTS:
            raise DerivationAuditLimitError(
                f"audit exceeds {_MAX_VISITED_OBJECTS} retained objects"
            )
        self._audit_intrinsic(value, path)
        self._audit_common(value, path)
        for field_info in fields(value):
            self._walk(
                getattr(value, field_info.name), f"{path}.{field_info.name}"
            )

    def _audit_intrinsic(self, value: object, path: str) -> None:
        post_init = getattr(value, "__post_init__", None)
        if post_init is None:
            return
        try:
            post_init()
        except (AssertionError, TypeError, ValueError) as error:
            self._add(
                DerivationAuditFindingCode.INTRINSIC_CONTRACT_VIOLATION,
                path,
                f"{type(value).__name__} violates its intrinsic "
                f"contract: {error}",
                _object_id(value),
            )

    def _audit_common(self, value: object, path: str) -> None:
        object_id = _object_id(value)
        if isinstance(value, SourceDocument) and value != self.source:
            self._add(
                DerivationAuditFindingCode.SOURCE_DOCUMENT_MISMATCH,
                path,
                "embedded source document differs from the audit root source",
                value.source_id,
            )
        source_id = getattr(value, "source_id", None)
        if source_id is not None and source_id != self.source.source_id:
            self._add(
                DerivationAuditFindingCode.SOURCE_ID_MISMATCH,
                f"{path}.source_id",
                "derived object refers to a different source ID",
                object_id,
            )
        source_blob_id = getattr(value, "source_blob_id", None)
        if source_blob_id is not None and source_blob_id != self.source.blob_id:
            self._add(
                DerivationAuditFindingCode.SOURCE_BLOB_MISMATCH,
                f"{path}.source_blob_id",
                "derived object refers to a different source blob",
                object_id,
            )
        source_hash = getattr(value, "source_content_hash", None)
        if source_hash is not None and source_hash != self.source.content_hash:
            self._add(
                DerivationAuditFindingCode.SOURCE_HASH_MISMATCH,
                f"{path}.source_content_hash",
                "derived object refers to a different source hash",
                object_id,
            )
        if isinstance(value, SourceSpan):
            self._audit_span(value, path)
        page_index = getattr(value, "page_index", None)
        if isinstance(page_index, int) and not isinstance(page_index, bool):
            if page_index not in self.pages:
                self._add(
                    DerivationAuditFindingCode.PAGE_OUT_OF_RANGE,
                    f"{path}.page_index",
                    "derived object refers to a page outside the root document",
                    object_id,
                    (("page_index", str(page_index)),),
                )
            else:
                self._audit_source_boxes(value, path, page_index)
        self._audit_processor_identity(value, path)
        self._audit_content_identity(value, path)
        self._audit_block_references(value, path)

    def _audit_span(self, span: SourceSpan, path: str) -> None:
        page = self.pages.get(span.page_index)
        if page is None:
            return
        if (
            span.printed_page_label is not None
            and span.printed_page_label != page.printed_page_label
        ):
            self._add(
                DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                f"{path}.printed_page_label",
                "source span printed label differs from its root page",
                span.source_object_id,
            )
        if span.bounding_box is not None:
            self._check_box(
                span.bounding_box,
                page.width,
                page.height,
                path,
                span.source_object_id,
            )
        if (
            span.source_object_id in self.blocks
            and span.start_offset is not None
            and self.blocks[span.source_object_id].text is not None
            and span.end_offset is not None
            and span.end_offset
            > len(self.blocks[span.source_object_id].text or "")
        ):
            self._add(
                DerivationAuditFindingCode.REGION_OUT_OF_RANGE,
                path,
                "source span text offsets exceed the referenced block",
                span.source_object_id,
            )

    def _audit_source_boxes(
        self, value: object, path: str, page_index: int
    ) -> None:
        page = self.pages[page_index]
        page_width = getattr(value, "page_width", None)
        page_height = getattr(value, "page_height", None)
        if page_width is not None and page_width != page.width:
            self._add(
                DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                f"{path}.page_width",
                "derived page width differs from the root page",
                _object_id(value),
            )
        if page_height is not None and page_height != page.height:
            self._add(
                DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                f"{path}.page_height",
                "derived page height differs from the root page",
                _object_id(value),
            )
        coordinate_system = getattr(value, "coordinate_system", None)
        if (
            coordinate_system is not None
            and coordinate_system != page.coordinate_system
        ):
            self._add(
                DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                f"{path}.coordinate_system",
                "derived coordinate system differs from the root page",
                _object_id(value),
            )
        rotation = getattr(value, "rotation_degrees", None)
        if rotation is not None and rotation != page.rotation_degrees:
            self._add(
                DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                f"{path}.rotation_degrees",
                "derived page rotation differs from the root page",
                _object_id(value),
            )
        for name in (
            "bounding_box",
            "source_bounding_box",
            "effective_source_bounding_box",
        ):
            box = getattr(value, name, None)
            if box is not None:
                self._check_box(
                    box,
                    page.width,
                    page.height,
                    f"{path}.{name}",
                    _object_id(value),
                )
        start = getattr(value, "start", None)
        end = getattr(value, "end", None)
        if (
            isinstance(start, tuple)
            and len(start) == 2
            and isinstance(end, tuple)
            and len(end) == 2
        ):
            for point_name, point in (("start", start), ("end", end)):
                if (
                    any(
                        isinstance(item, bool)
                        or not isinstance(item, (int, float))
                        or not math.isfinite(item)
                        for item in point
                    )
                    or point[0] < -_BOX_TOLERANCE
                    or point[1] < -_BOX_TOLERANCE
                    or point[0] > page.width + _BOX_TOLERANCE
                    or point[1] > page.height + _BOX_TOLERANCE
                ):
                    self._add(
                        DerivationAuditFindingCode.REGION_OUT_OF_RANGE,
                        f"{path}.{point_name}",
                        "source point lies outside the root page extent",
                        _object_id(value),
                    )
        if isinstance(value, RenderedRegion):
            if value.page_rotation_degrees != page.rotation_degrees:
                self._add(
                    DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                    f"{path}.page_rotation_degrees",
                    "rendered region rotation differs from its root page",
                    value.region_id,
                )

    def _check_box(
        self,
        box: object,
        width: float,
        height: float,
        path: str,
        object_id: str | None,
    ) -> None:
        if (
            not isinstance(box, tuple)
            or len(box) != 4
            or any(
                isinstance(item, bool)
                or not isinstance(item, (int, float))
                or not math.isfinite(item)
                for item in box
            )
        ):
            self._add(
                DerivationAuditFindingCode.REGION_OUT_OF_RANGE,
                path,
                "source bounding box is not a finite four-coordinate tuple",
                object_id,
            )
            return
        x0, y0, x1, y1 = box
        if (
            x0 < -_BOX_TOLERANCE
            or y0 < -_BOX_TOLERANCE
            or x1 > width + _BOX_TOLERANCE
            or y1 > height + _BOX_TOLERANCE
            or x1 < x0
            or y1 < y0
        ):
            self._add(
                DerivationAuditFindingCode.REGION_OUT_OF_RANGE,
                path,
                "source bounding box lies outside the root page extent",
                object_id,
                (
                    ("box", repr(box)),
                    ("page_extent", repr((0.0, 0.0, width, height))),
                ),
            )

    def _audit_processor_identity(self, value: object, path: str) -> None:
        for prefix in ("processor", "backend", "extractor"):
            name_field = f"{prefix}_name"
            version_field = f"{prefix}_version"
            has_name = hasattr(value, name_field)
            has_version = hasattr(value, version_field)
            if not (has_name or has_version):
                continue
            name = getattr(value, name_field, None)
            version = getattr(value, version_field, None)
            if (
                not isinstance(name, str)
                or not name
                or not isinstance(version, str)
                or not version
            ):
                self._add(
                    DerivationAuditFindingCode.PROCESSOR_IDENTITY_MISSING,
                    path,
                    f"{prefix} name and version must both be non-empty",
                    _object_id(value),
                )
        if hasattr(value, "configuration_digest"):
            digest = value.configuration_digest
            if not isinstance(digest, str) or not digest:
                self._add(
                    DerivationAuditFindingCode.PROCESSOR_IDENTITY_MISSING,
                    f"{path}.configuration_digest",
                    "processor configuration digest is missing",
                    _object_id(value),
                )
        if hasattr(value, "contract_version"):
            contract_version = value.contract_version
            if not isinstance(contract_version, str) or not contract_version:
                self._add(
                    DerivationAuditFindingCode.CONTRACT_VERSION_MISSING,
                    f"{path}.contract_version",
                    "artifact contract version is missing",
                    _object_id(value),
                )

    def _audit_content_identity(self, value: object, path: str) -> None:
        if not all(
            hasattr(value, name)
            for name in ("content", "content_sha256", "byte_length")
        ):
            return
        content_value: Any = value
        content = content_value.content
        digest = content_value.content_sha256
        byte_length = content_value.byte_length
        if isinstance(content, bytes) and (
            hashlib.sha256(content).hexdigest() != digest
            or len(content) != byte_length
        ):
            self._add(
                DerivationAuditFindingCode.CONTENT_IDENTITY_MISMATCH,
                path,
                "retained content bytes do not match their hash or byte length",
                _object_id(value),
            )

    def _audit_block_references(self, value: object, path: str) -> None:
        if isinstance(value, ExtractedBlock):
            return
        for field_name in ("block_id", "source_block_id"):
            block_id = getattr(value, field_name, None)
            if isinstance(block_id, str) and block_id not in self.blocks:
                self._orphan(f"{path}.{field_name}", block_id)
        for field_name in (
            "block_ids",
            "source_block_ids",
            "input_block_ids",
            "raw_block_ids",
            "non_text_block_ids",
            "merged_cell_signal_block_ids",
        ):
            block_ids = getattr(value, field_name, None)
            if isinstance(block_ids, tuple):
                for block_id in block_ids:
                    if (
                        isinstance(block_id, str)
                        and block_id not in self.blocks
                    ):
                        self._orphan(f"{path}.{field_name}", block_id)

    def _require_root_document(
        self, document: ExtractedDocument, path: str
    ) -> None:
        if document != self.document:
            self._add(
                DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                path,
                "embedded extraction document differs from the audit "
                "root document",
                document.document_id,
            )

    def _require_registered(
        self,
        artifact: object,
        registry: dict[str, Any],
        identity: str,
        path: str,
    ) -> None:
        registered = registry.get(identity)
        if registered is None:
            self._add(
                DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISSING,
                path,
                "required upstream artifact is absent from the audit input",
                identity,
            )
        elif registered != artifact:
            self._add(
                DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                path,
                "embedded upstream artifact differs from its "
                "registered artifact",
                identity,
            )

    def _orphan(self, path: str, object_id: str) -> None:
        self._add(
            DerivationAuditFindingCode.ORPHAN_OBJECT_REFERENCE,
            path,
            "derived object refers to an unknown upstream object",
            object_id,
        )

    def _add(
        self,
        code: DerivationAuditFindingCode,
        path: str,
        message: str,
        object_id: str | None = None,
        evidence: Metadata = (),
    ) -> None:
        normalized_evidence = tuple(sorted(evidence))
        key = (code, path, object_id, normalized_evidence)
        if key in self._finding_keys:
            return
        if len(self.findings) >= _MAX_FINDINGS:
            raise DerivationAuditLimitError(
                f"audit exceeds {_MAX_FINDINGS} findings"
            )
        self._finding_keys.add(key)
        self.findings.append(
            DerivationAuditFinding.create(
                code=code,
                path=path,
                message=message,
                object_id=object_id,
                evidence=normalized_evidence,
            )
        )


def _artifact_id(value: object) -> str:
    for name in (
        "result_id",
        "analysis_id",
        "manifest_id",
        "artifact_id",
        "document_id",
    ):
        identity = getattr(value, name, None)
        if isinstance(identity, str) and identity:
            return identity
    return stable_id(
        "derivation-audit-anonymous-artifact", type(value).__name__
    )


def _object_id(value: object) -> str | None:
    for name in (
        "result_id",
        "analysis_id",
        "artifact_id",
        "document_id",
        "manifest_id",
        "candidate_id",
        "structure_id",
        "item_id",
        "region_id",
        "block_id",
        "node_id",
        "selection_result_id",
        "selection_id",
        "work_item_id",
        "request_id",
        "input_id",
        "page_id",
        "source_id",
    ):
        identity = getattr(value, name, None)
        if isinstance(identity, str) and identity:
            return identity
    return None
