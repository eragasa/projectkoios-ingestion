from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from projectkoios.base import (
    DataObjectActionizer,
    DataObjectActionRequest,
    DataObjectActionResult,
)
from projectkoios.ingestion.clean_transcript import CleanTranscript
from projectkoios.ingestion.equations.detection import EquationDetectionResult
from projectkoios.ingestion.figures import FigureDetectionResult
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout import PageLayoutResult
from projectkoios.ingestion.models import (
    ExtractedDocument,
    ExtractionResult,
    Metadata,
    SourceDocument,
)
from projectkoios.ingestion.ocr.result import OCRResult
from projectkoios.ingestion.processing import ProcessingResult
from projectkoios.ingestion.provenance.common import (
    _artifact_id,
    _object_id,
)
from projectkoios.ingestion.reconciliation.result import OCRReconciliationResult
from projectkoios.ingestion.structure import StructureAnalysis
from projectkoios.ingestion.tables import TableDetectionResult
from projectkoios.ingestion.tables.structure.result import TableStructureResult
from projectkoios.ingestion.transcription.result.result import (
    StructuredTranscriptionResult,
)

DERIVATION_AUDIT_CONTRACT_VERSION = "1.0"
DERIVATION_AUDIT_PROCESSOR_VERSION = "3"
DERIVATION_AUDIT_ACTION_CONTRACT_VERSION = "1.0"
DERIVATION_AUDIT_ACTIONIZER_NAME = "deterministic-derivation-audit-actionizer"
DERIVATION_AUDIT_ACTIONIZER_VERSION = "1"
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
    ocr_results: tuple[OCRResult, ...] = ()
    reconciliation_results: tuple[OCRReconciliationResult, ...] = ()
    layout_results: tuple[PageLayoutResult, ...] = ()
    structure_analyses: tuple[StructureAnalysis, ...] = ()
    equation_results: tuple[EquationDetectionResult, ...] = ()
    table_detection_results: tuple[TableDetectionResult, ...] = ()
    table_structure_results: tuple[TableStructureResult, ...] = ()
    figure_results: tuple[FigureDetectionResult, ...] = ()
    processing_results: tuple[ProcessingResult, ...] = ()
    transcription_results: tuple[StructuredTranscriptionResult, ...] = ()
    clean_transcripts: tuple[CleanTranscript, ...] = ()
    contract_version: str = DERIVATION_AUDIT_CONTRACT_VERSION

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
    "ocr_results": OCRResult,
    "reconciliation_results": OCRReconciliationResult,
    "layout_results": PageLayoutResult,
    "structure_analyses": StructureAnalysis,
    "equation_results": EquationDetectionResult,
    "table_detection_results": TableDetectionResult,
    "table_structure_results": TableStructureResult,
    "figure_results": FigureDetectionResult,
    "processing_results": ProcessingResult,
    "transcription_results": StructuredTranscriptionResult,
    "clean_transcripts": CleanTranscript,
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
    "clean_transcripts",
)


@dataclass(frozen=True, slots=True)
class DerivationAuditRequest(DataObjectActionRequest):
    """Complete immutable intent for one bounded derivation audit."""

    request_id: str
    audit_input: DerivationAuditInput
    contract_version: str = DERIVATION_AUDIT_ACTION_CONTRACT_VERSION

    @classmethod
    def create(
        cls, *, audit_input: DerivationAuditInput
    ) -> DerivationAuditRequest:
        if not isinstance(audit_input, DerivationAuditInput):
            raise TypeError("audit_input must be DerivationAuditInput")
        return cls(
            request_id=cls._request_id(audit_input),
            audit_input=audit_input,
        )

    def __post_init__(self) -> None:
        if self.contract_version != DERIVATION_AUDIT_ACTION_CONTRACT_VERSION:
            raise ValueError("unsupported derivation-audit request contract")
        if not isinstance(self.audit_input, DerivationAuditInput):
            raise TypeError("audit_input must be DerivationAuditInput")
        if self.request_id != self._request_id(self.audit_input):
            raise ValueError("derivation-audit request ID is inconsistent")

    @staticmethod
    def _request_id(audit_input: DerivationAuditInput) -> str:
        return stable_id(
            "derivation-audit-request",
            hashlib.sha256(audit_input.source_content).hexdigest(),
            len(audit_input.source_content),
            audit_input.extraction_result.manifest.manifest_id,
            tuple(
                (
                    name,
                    tuple(
                        _artifact_id(item)
                        for item in getattr(audit_input, name)
                    ),
                )
                for name in _LAYER_FIELDS
            ),
            audit_input.contract_version,
            DERIVATION_AUDIT_ACTION_CONTRACT_VERSION,
        )


@dataclass(frozen=True, slots=True)
class DerivationAuditResult(DataObjectActionResult):
    """Identified outcome of one exact derivation-audit request."""

    result_id: str
    request_id: str
    report: DerivationAuditReport
    actionizer_name: str
    actionizer_version: str
    contract_version: str = DERIVATION_AUDIT_ACTION_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        request: DerivationAuditRequest,
        report: DerivationAuditReport,
        actionizer_name: str,
        actionizer_version: str,
    ) -> DerivationAuditResult:
        if not isinstance(request, DerivationAuditRequest):
            raise TypeError("request must be DerivationAuditRequest")
        if not isinstance(report, DerivationAuditReport):
            raise TypeError("report must be DerivationAuditReport")
        result_id = stable_id(
            "derivation-audit-action-result",
            request.request_id,
            report.report_id,
            actionizer_name,
            actionizer_version,
            DERIVATION_AUDIT_ACTION_CONTRACT_VERSION,
        )
        return cls(
            result_id=result_id,
            request_id=request.request_id,
            report=report,
            actionizer_name=actionizer_name,
            actionizer_version=actionizer_version,
        )

    @property
    def status(self) -> DerivationAuditStatus:
        return self.report.status

    @property
    def valid(self) -> bool:
        return self.report.valid

    def require_valid(self) -> None:
        self.report.require_valid()

    def __post_init__(self) -> None:
        if self.contract_version != DERIVATION_AUDIT_ACTION_CONTRACT_VERSION:
            raise ValueError("unsupported derivation-audit result contract")
        if not isinstance(self.report, DerivationAuditReport):
            raise TypeError("report must be DerivationAuditReport")
        if not self.request_id:
            raise ValueError("request_id must be non-empty")
        if not self.actionizer_name or not self.actionizer_version:
            raise ValueError("actionizer identity must be complete")
        expected = stable_id(
            "derivation-audit-action-result",
            self.request_id,
            self.report.report_id,
            self.actionizer_name,
            self.actionizer_version,
            self.contract_version,
        )
        if self.result_id != expected:
            raise ValueError("derivation-audit result ID is inconsistent")


@dataclass
class _Registry:
    layouts: dict[str, PageLayoutResult]
    structures: dict[str, StructureAnalysis]
    ocr_results: dict[str, OCRResult]
    equations: dict[str, EquationDetectionResult]
    table_detections: dict[str, TableDetectionResult]
    table_structures: dict[str, TableStructureResult]
    figures: dict[str, FigureDetectionResult]
    processing: dict[str, ProcessingResult]
    transcriptions: dict[str, StructuredTranscriptionResult]
    clean_transcripts: dict[str, CleanTranscript]


from projectkoios.ingestion.provenance.domains import (  # noqa: E402
    _DomainAuditWalker,
)
from projectkoios.ingestion.provenance.walker import (  # noqa: E402
    _ContractAuditWalker,
)


class DerivationAuditValidator(
    DataObjectActionizer[DerivationAuditRequest, DerivationAuditResult]
):
    """Validate exact transitive provenance without changing any artifact."""

    __slots__ = ()

    actionizer_name = DERIVATION_AUDIT_ACTIONIZER_NAME
    actionizer_version = DERIVATION_AUDIT_ACTIONIZER_VERSION
    name = "deterministic-derivation-audit-validator"
    version = DERIVATION_AUDIT_PROCESSOR_VERSION

    def action(
        self, *, request: DerivationAuditRequest
    ) -> DerivationAuditResult:
        """Return one identified result for an exact audit request."""
        if not isinstance(request, DerivationAuditRequest):
            raise TypeError("request must be DerivationAuditRequest")
        processor_version = self._processor_version(
            audit_input=request.audit_input
        )
        report = self._audit(
            audit_input=request.audit_input,
            processor_version=processor_version,
        )
        return DerivationAuditResult.create(
            request=request,
            report=report,
            actionizer_name=self.actionizer_name,
            actionizer_version=self.actionizer_version,
        )

    def execute(
        self, *, request: DerivationAuditRequest
    ) -> DerivationAuditResult:
        """Preserve the pre-ABC actionizer spelling for compatibility."""
        return self.action(request=request)

    def audit(self, audit_input: DerivationAuditInput) -> DerivationAuditReport:
        """Preserve the established audit API during taxonomy migration."""
        if not isinstance(audit_input, DerivationAuditInput):
            raise TypeError("audit_input must be DerivationAuditInput")
        return self._audit(
            audit_input=audit_input,
            processor_version=self._processor_version(audit_input=audit_input),
        )

    def validate(self, audit_input: DerivationAuditInput) -> None:
        self.audit(audit_input).require_valid()

    def _processor_version(self, *, audit_input: DerivationAuditInput) -> str:
        return self.version

    def _audit(
        self,
        *,
        audit_input: DerivationAuditInput,
        processor_version: str,
    ) -> DerivationAuditReport:
        state = _AuditState(audit_input, self.name, processor_version)
        state.run()
        return state.report()


class _AuditState(_DomainAuditWalker, _ContractAuditWalker):
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
                audit_input.clean_transcripts,
                "result_id",
                "clean_transcripts",
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


_COMPATIBILITY_TYPES = (
    DerivationAuditError,
    DerivationAuditFinding,
    DerivationAuditFindingCode,
    DerivationAuditInput,
    DerivationAuditLimitError,
    DerivationAuditReport,
    DerivationAuditStatus,
    DerivationAuditValidator,
)
for _compatibility_type in _COMPATIBILITY_TYPES:
    _compatibility_type.__module__ = "projectkoios.ingestion.provenance"
del _compatibility_type


__all__ = [
    "DERIVATION_AUDIT_ACTION_CONTRACT_VERSION",
    "DERIVATION_AUDIT_ACTIONIZER_NAME",
    "DERIVATION_AUDIT_ACTIONIZER_VERSION",
    "DERIVATION_AUDIT_CONTRACT_VERSION",
    "DERIVATION_AUDIT_PROCESSOR_VERSION",
    "DerivationAuditError",
    "DerivationAuditFinding",
    "DerivationAuditFindingCode",
    "DerivationAuditInput",
    "DerivationAuditLimitError",
    "DerivationAuditReport",
    "DerivationAuditRequest",
    "DerivationAuditResult",
    "DerivationAuditStatus",
    "DerivationAuditValidator",
]
