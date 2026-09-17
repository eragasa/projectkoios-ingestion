from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum, StrEnum
from typing import TYPE_CHECKING

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import (
    ExtractedDocument,
    ExtractedPage,
    Metadata,
    SourceDocument,
    SourceSpan,
    WarningSeverity,
)
from projectkoios.ingestion.structure import StructureAnalysis, StructureNode

if TYPE_CHECKING:
    from projectkoios.ingestion.protocols import (
        DerivedProcessingCache,
        ProcessingProcessor,
    )

PROCESSING_CONTRACT_VERSION = "1.0"
PROCESSING_COORDINATOR_VERSION = "1"
PROCESSING_CONFIGURATION_VERSION = "1"
_MAX_SELECTIONS = 256
_MAX_PAGE_RANGES = 256
_MAX_SOURCE_SPANS = 16_384
_MAX_STRUCTURE_NODES = 4_096
_MAX_SELECTED_PAGES = 4_096
_MAX_INPUT_OBJECT_IDS = 65_536
_MAX_ATTEMPTS = 8
_MAX_ARTIFACTS_PER_SELECTION = 4_096
_MAX_ARTIFACT_BYTES = 32_000_000
_MAX_TOTAL_ARTIFACT_BYTES = 100_000_000
_MAX_WARNINGS_PER_ATTEMPT = 256
_MAX_FAILURES_PER_ATTEMPT = 64
_MAX_TOTAL_WARNINGS = 4_096
_MAX_TOTAL_FAILURES = 1_024
_MAX_MESSAGE_CHARACTERS = 65_536
_MAX_METADATA_ENTRIES = 256
_MAX_METADATA_CHARACTERS = 1_000_000
_MAX_RESOURCES = 64
_MAX_IDENTITY_CHARACTERS = 4_096
_MAX_RESULT_BYTES = 128_000_000


class ProcessingLimitError(ValueError):
    """Raised before JIT coordination exceeds a configured hard bound."""


class ProcessingCoordinatorError(RuntimeError):
    """Raised when coordination cannot truthfully produce a bounded result."""


class ProcessingStatus(StrEnum):
    """Execution status; never semantic or human acceptance."""

    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class ProcessingFailureKind(StrEnum):
    INPUT_REJECTED = "input_rejected"
    STALE_INPUT = "stale_input"
    RESOURCE_LIMIT = "resource_limit"
    PROCESSOR_UNAVAILABLE = "processor_unavailable"
    PROCESSOR_ERROR = "processor_error"
    OUTPUT_INVALID = "output_invalid"
    OUTPUT_INCOMPLETE = "output_incomplete"


class ProcessingResourceIdentityKind(StrEnum):
    SHA256 = "sha256"
    EXPLICIT = "explicit"


@dataclass(frozen=True)
class ProcessingPhysicalPageRange:
    range_id: str
    start_page_index: int
    end_page_index: int
    contract_version: str = PROCESSING_CONTRACT_VERSION

    @classmethod
    def create(
        cls, *, start_page_index: int, end_page_index: int
    ) -> ProcessingPhysicalPageRange:
        return cls(
            range_id=stable_id(
                "processing-physical-page-range",
                start_page_index,
                end_page_index,
            ),
            start_page_index=start_page_index,
            end_page_index=end_page_index,
        )

    def __post_init__(self) -> None:
        if self.contract_version != PROCESSING_CONTRACT_VERSION:
            raise ValueError("unsupported physical-page-range version")
        _nonnegative_integer("start_page_index", self.start_page_index)
        _nonnegative_integer("end_page_index", self.end_page_index)
        if self.end_page_index < self.start_page_index:
            raise ValueError("physical page range must be ordered")
        expected = stable_id(
            "processing-physical-page-range",
            self.start_page_index,
            self.end_page_index,
        )
        if self.range_id != expected:
            raise ValueError("physical page range ID is inconsistent")


@dataclass(frozen=True)
class ProcessingPrintedPageRange:
    range_id: str
    start_printed_page_label: str
    end_printed_page_label: str
    contract_version: str = PROCESSING_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        start_printed_page_label: str,
        end_printed_page_label: str,
    ) -> ProcessingPrintedPageRange:
        return cls(
            range_id=stable_id(
                "processing-printed-page-range",
                start_printed_page_label,
                end_printed_page_label,
            ),
            start_printed_page_label=start_printed_page_label,
            end_printed_page_label=end_printed_page_label,
        )

    def __post_init__(self) -> None:
        if self.contract_version != PROCESSING_CONTRACT_VERSION:
            raise ValueError("unsupported printed-page-range version")
        _bounded_string(
            "start printed page label",
            self.start_printed_page_label,
            nonempty=True,
        )
        _bounded_string(
            "end printed page label",
            self.end_printed_page_label,
            nonempty=True,
        )
        expected = stable_id(
            "processing-printed-page-range",
            self.start_printed_page_label,
            self.end_printed_page_label,
        )
        if self.range_id != expected:
            raise ValueError("printed page range ID is inconsistent")


@dataclass(frozen=True)
class ProcessingConfiguration:
    configuration_version: str = PROCESSING_CONFIGURATION_VERSION
    max_selections: int = _MAX_SELECTIONS
    max_page_ranges_per_selection: int = _MAX_PAGE_RANGES
    max_source_spans_per_selection: int = _MAX_SOURCE_SPANS
    max_structure_nodes_per_selection: int = _MAX_STRUCTURE_NODES
    max_selected_pages_per_selection: int = _MAX_SELECTED_PAGES
    max_input_object_ids_per_selection: int = _MAX_INPUT_OBJECT_IDS
    max_attempts_per_selection: int = 2
    max_artifacts_per_selection: int = _MAX_ARTIFACTS_PER_SELECTION
    max_artifact_bytes: int = _MAX_ARTIFACT_BYTES
    max_total_artifact_bytes: int = _MAX_TOTAL_ARTIFACT_BYTES
    max_warnings_per_attempt: int = _MAX_WARNINGS_PER_ATTEMPT
    max_failures_per_attempt: int = _MAX_FAILURES_PER_ATTEMPT
    max_total_warnings: int = _MAX_TOTAL_WARNINGS
    max_total_failures: int = _MAX_TOTAL_FAILURES
    max_message_characters: int = _MAX_MESSAGE_CHARACTERS
    max_metadata_entries: int = _MAX_METADATA_ENTRIES
    max_metadata_characters: int = _MAX_METADATA_CHARACTERS
    max_resources: int = _MAX_RESOURCES
    max_result_bytes: int = _MAX_RESULT_BYTES

    def __post_init__(self) -> None:
        if self.configuration_version != PROCESSING_CONFIGURATION_VERSION:
            raise ValueError("unsupported processing configuration version")
        for name, hard_limit in (
            ("max_selections", _MAX_SELECTIONS),
            ("max_page_ranges_per_selection", _MAX_PAGE_RANGES),
            ("max_source_spans_per_selection", _MAX_SOURCE_SPANS),
            ("max_structure_nodes_per_selection", _MAX_STRUCTURE_NODES),
            ("max_selected_pages_per_selection", _MAX_SELECTED_PAGES),
            (
                "max_input_object_ids_per_selection",
                _MAX_INPUT_OBJECT_IDS,
            ),
            ("max_attempts_per_selection", _MAX_ATTEMPTS),
            ("max_artifacts_per_selection", _MAX_ARTIFACTS_PER_SELECTION),
            ("max_artifact_bytes", _MAX_ARTIFACT_BYTES),
            ("max_total_artifact_bytes", _MAX_TOTAL_ARTIFACT_BYTES),
            ("max_warnings_per_attempt", _MAX_WARNINGS_PER_ATTEMPT),
            ("max_failures_per_attempt", _MAX_FAILURES_PER_ATTEMPT),
            ("max_total_warnings", _MAX_TOTAL_WARNINGS),
            ("max_total_failures", _MAX_TOTAL_FAILURES),
            ("max_message_characters", _MAX_MESSAGE_CHARACTERS),
            ("max_metadata_entries", _MAX_METADATA_ENTRIES),
            ("max_metadata_characters", _MAX_METADATA_CHARACTERS),
            ("max_resources", _MAX_RESOURCES),
            ("max_result_bytes", _MAX_RESULT_BYTES),
        ):
            value = getattr(self, name)
            _positive_integer(name, value)
            if value > hard_limit:
                raise ProcessingLimitError(
                    f"{name} exceeds its implementation maximum ({hard_limit})"
                )

    @property
    def configuration_digest(self) -> str:
        return stable_id("processing-configuration", self.identity_parts())

    def identity_parts(self) -> tuple[object, ...]:
        return tuple(
            (name, getattr(self, name)) for name in self.__dataclass_fields__
        )


@dataclass(frozen=True)
class ProcessingSelection:
    selection_id: str
    document: ExtractedDocument
    source_spans: tuple[SourceSpan, ...] = ()
    physical_page_ranges: tuple[ProcessingPhysicalPageRange, ...] = ()
    printed_page_ranges: tuple[ProcessingPrintedPageRange, ...] = ()
    structure_analysis: StructureAnalysis | None = None
    structure_node_ids: tuple[str, ...] = ()
    contract_version: str = PROCESSING_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        document: ExtractedDocument,
        source_spans: tuple[SourceSpan, ...] = (),
        physical_page_ranges: tuple[ProcessingPhysicalPageRange, ...] = (),
        printed_page_ranges: tuple[ProcessingPrintedPageRange, ...] = (),
        structure_analysis: StructureAnalysis | None = None,
        structure_node_ids: tuple[str, ...] = (),
    ) -> ProcessingSelection:
        evidence = _resolve_selection_evidence(
            document,
            source_spans,
            physical_page_ranges,
            printed_page_ranges,
            structure_analysis,
            structure_node_ids,
        )
        return cls(
            selection_id=_selection_id(
                document,
                source_spans,
                physical_page_ranges,
                printed_page_ranges,
                evidence.selected_pages,
                structure_analysis,
                evidence.selected_nodes,
            ),
            document=document,
            source_spans=source_spans,
            physical_page_ranges=physical_page_ranges,
            printed_page_ranges=printed_page_ranges,
            structure_analysis=structure_analysis,
            structure_node_ids=structure_node_ids,
        )

    def __post_init__(self) -> None:
        if self.contract_version != PROCESSING_CONTRACT_VERSION:
            raise ValueError("unsupported processing selection version")
        evidence = _resolve_selection_evidence(
            self.document,
            self.source_spans,
            self.physical_page_ranges,
            self.printed_page_ranges,
            self.structure_analysis,
            self.structure_node_ids,
        )
        expected = _selection_id(
            self.document,
            self.source_spans,
            self.physical_page_ranges,
            self.printed_page_ranges,
            evidence.selected_pages,
            self.structure_analysis,
            evidence.selected_nodes,
        )
        if self.selection_id != expected:
            raise ValueError("processing selection ID is inconsistent")


@dataclass(frozen=True)
class _ResolvedSelectionEvidence:
    selected_pages: tuple[ExtractedPage, ...]
    selected_nodes: tuple[StructureNode, ...]


@dataclass(frozen=True)
class ProcessingWorkItem:
    work_item_id: str
    selection_id: str
    source: SourceDocument
    full_pages: tuple[ExtractedPage, ...]
    source_spans: tuple[SourceSpan, ...]
    structure_nodes: tuple[StructureNode, ...]
    input_object_ids: tuple[str, ...]
    contract_version: str = PROCESSING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != PROCESSING_CONTRACT_VERSION:
            raise ValueError("unsupported processing work-item version")
        _identity_fields(self.selection_id)
        if not isinstance(self.source, SourceDocument):
            raise TypeError("work item source must be SourceDocument")
        _require_tuple("full pages", self.full_pages)
        _require_tuple("source spans", self.source_spans)
        _require_tuple("structure nodes", self.structure_nodes)
        _unique_strings("input object IDs", self.input_object_ids)
        if any(not isinstance(page, ExtractedPage) for page in self.full_pages):
            raise TypeError("full pages contain an unsupported value")
        page_indices = tuple(page.page_index for page in self.full_pages)
        if page_indices != tuple(sorted(set(page_indices))):
            raise ValueError("full pages must have unique ascending indices")
        if any(not isinstance(span, SourceSpan) for span in self.source_spans):
            raise TypeError("source spans contain an unsupported value")
        if any(
            span.source_id != self.source.source_id
            or span.source_blob_id != self.source.blob_id
            for span in self.source_spans
        ):
            raise ValueError("work-item spans must refer to the exact source")
        if any(
            not isinstance(node, StructureNode) for node in self.structure_nodes
        ):
            raise TypeError("structure nodes contain an unsupported value")
        if any(
            span.source_id != self.source.source_id
            or span.source_blob_id != self.source.blob_id
            for node in self.structure_nodes
            for span in node.source_spans
        ):
            raise ValueError("work-item nodes must refer to the exact source")
        expected = _work_item_id(
            self.selection_id,
            self.source,
            self.full_pages,
            self.source_spans,
            self.structure_nodes,
            self.input_object_ids,
        )
        if self.work_item_id != expected:
            raise ValueError("processing work-item ID is inconsistent")

    @property
    def full_page_indices(self) -> tuple[int, ...]:
        return tuple(page.page_index for page in self.full_pages)


@dataclass(frozen=True)
class ProcessingResourceIdentity:
    resource_name: str
    identity_kind: ProcessingResourceIdentityKind
    resource_identity: str

    def __post_init__(self) -> None:
        _bounded_string("resource name", self.resource_name, nonempty=True)
        if not isinstance(self.identity_kind, ProcessingResourceIdentityKind):
            raise TypeError("unsupported processing resource identity kind")
        _bounded_string(
            "resource identity", self.resource_identity, nonempty=True
        )
        if self.identity_kind is ProcessingResourceIdentityKind.SHA256:
            _sha256("resource identity", self.resource_identity)

    def identity_parts(self) -> tuple[object, ...]:
        return (
            self.resource_name,
            self.identity_kind.value,
            self.resource_identity,
        )


@dataclass(frozen=True)
class ProcessingProcessorIdentity:
    processor_name: str
    processor_version: str
    backend_name: str
    backend_version: str
    configuration_digest: str
    resources: tuple[ProcessingResourceIdentity, ...] = ()

    def __post_init__(self) -> None:
        _identity_fields(
            self.processor_name,
            self.processor_version,
            self.backend_name,
            self.backend_version,
            self.configuration_digest,
        )
        _require_tuple("resources", self.resources)
        if len(self.resources) > _MAX_RESOURCES:
            raise ProcessingLimitError("too many processing resources")
        if any(
            not isinstance(item, ProcessingResourceIdentity)
            for item in self.resources
        ):
            raise TypeError("resources contain an unsupported value")
        names = tuple(item.resource_name for item in self.resources)
        if len(set(names)) != len(names):
            raise ValueError("processing resource names must be unique")
        if names != tuple(sorted(names)):
            raise ValueError("processing resources must be ordered by name")

    @property
    def identity_digest(self) -> str:
        return stable_id("processing-processor", self.identity_parts())

    def identity_parts(self) -> tuple[object, ...]:
        return (
            self.processor_name,
            self.processor_version,
            self.backend_name,
            self.backend_version,
            self.configuration_digest,
            tuple(item.identity_parts() for item in self.resources),
        )


@dataclass(frozen=True)
class ProcessingDerivedArtifact:
    artifact_id: str
    work_item_id: str
    artifact_kind: str
    media_type: str
    content_sha256: str
    byte_length: int
    content: bytes
    input_object_ids: tuple[str, ...]
    source_spans: tuple[SourceSpan, ...]
    evidence: Metadata = ()
    contract_version: str = PROCESSING_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        work_item: ProcessingWorkItem,
        artifact_kind: str,
        media_type: str,
        content: bytes,
        input_object_ids: tuple[str, ...] = (),
        source_spans: tuple[SourceSpan, ...] = (),
        evidence: Metadata = (),
    ) -> ProcessingDerivedArtifact:
        if not isinstance(content, bytes):
            raise TypeError(
                "processing artifact content must be immutable bytes"
            )
        digest = _bytes_sha256(content)
        artifact_id = stable_id(
            "processing-derived-artifact",
            work_item.work_item_id,
            artifact_kind,
            media_type,
            digest,
            len(content),
            input_object_ids,
            tuple(_span_parts(span) for span in source_spans),
            evidence,
        )
        return cls(
            artifact_id=artifact_id,
            work_item_id=work_item.work_item_id,
            artifact_kind=artifact_kind,
            media_type=media_type,
            content_sha256=digest,
            byte_length=len(content),
            content=content,
            input_object_ids=input_object_ids,
            source_spans=source_spans,
            evidence=evidence,
        )

    def __post_init__(self) -> None:
        if self.contract_version != PROCESSING_CONTRACT_VERSION:
            raise ValueError("unsupported processing artifact version")
        _identity_fields(self.work_item_id, self.artifact_kind, self.media_type)
        if not isinstance(self.content, bytes):
            raise TypeError(
                "processing artifact content must be immutable bytes"
            )
        if len(self.content) > _MAX_ARTIFACT_BYTES:
            raise ProcessingLimitError("processing artifact exceeds hard limit")
        if self.byte_length != len(self.content):
            raise ValueError("processing artifact byte length is inconsistent")
        if self.content_sha256 != _bytes_sha256(self.content):
            raise ValueError("processing artifact digest is inconsistent")
        _unique_strings("artifact input object IDs", self.input_object_ids)
        _require_tuple("artifact source spans", self.source_spans)
        if any(not isinstance(span, SourceSpan) for span in self.source_spans):
            raise TypeError(
                "artifact source spans contain an unsupported value"
            )
        _validate_metadata(self.evidence)
        if not self.input_object_ids and not self.source_spans:
            raise ValueError("processing artifact requires source provenance")
        expected = stable_id(
            "processing-derived-artifact",
            self.work_item_id,
            self.artifact_kind,
            self.media_type,
            self.content_sha256,
            self.byte_length,
            self.input_object_ids,
            tuple(_span_parts(span) for span in self.source_spans),
            self.evidence,
        )
        if self.artifact_id != expected:
            raise ValueError("processing artifact ID is inconsistent")


@dataclass(frozen=True)
class ProcessingWarning:
    warning_id: str
    work_item_id: str
    code: str
    severity: WarningSeverity
    message: str
    object_ids: tuple[str, ...] = ()
    source_spans: tuple[SourceSpan, ...] = ()
    evidence: Metadata = ()
    suggested_recovery: str | None = None
    contract_version: str = PROCESSING_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        work_item: ProcessingWorkItem,
        code: str,
        severity: WarningSeverity,
        message: str,
        object_ids: tuple[str, ...] = (),
        source_spans: tuple[SourceSpan, ...] = (),
        evidence: Metadata = (),
        suggested_recovery: str | None = None,
    ) -> ProcessingWarning:
        warning_id = stable_id(
            "processing-warning",
            work_item.work_item_id,
            code,
            severity.value,
            message,
            object_ids,
            tuple(_span_parts(span) for span in source_spans),
            evidence,
            suggested_recovery,
        )
        return cls(
            warning_id=warning_id,
            work_item_id=work_item.work_item_id,
            code=code,
            severity=severity,
            message=message,
            object_ids=object_ids,
            source_spans=source_spans,
            evidence=evidence,
            suggested_recovery=suggested_recovery,
        )

    def __post_init__(self) -> None:
        if self.contract_version != PROCESSING_CONTRACT_VERSION:
            raise ValueError("unsupported processing warning version")
        _identity_fields(self.work_item_id, self.code)
        if not isinstance(self.severity, WarningSeverity):
            raise TypeError("processing warning severity is unsupported")
        _bounded_string(
            "processing warning message",
            self.message,
            nonempty=True,
            limit=_MAX_MESSAGE_CHARACTERS,
        )
        _unique_strings("warning object IDs", self.object_ids)
        _validate_span_tuple("warning source spans", self.source_spans)
        _validate_metadata(self.evidence)
        if self.suggested_recovery is not None:
            _bounded_string(
                "suggested recovery",
                self.suggested_recovery,
                nonempty=True,
                limit=_MAX_MESSAGE_CHARACTERS,
            )
        expected = stable_id(
            "processing-warning",
            self.work_item_id,
            self.code,
            self.severity.value,
            self.message,
            self.object_ids,
            tuple(_span_parts(span) for span in self.source_spans),
            self.evidence,
            self.suggested_recovery,
        )
        if self.warning_id != expected:
            raise ValueError("processing warning ID is inconsistent")


@dataclass(frozen=True)
class ProcessingFailure:
    failure_id: str
    work_item_id: str
    kind: ProcessingFailureKind
    message: str
    retryable: bool
    object_ids: tuple[str, ...] = ()
    source_spans: tuple[SourceSpan, ...] = ()
    evidence: Metadata = ()
    contract_version: str = PROCESSING_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        work_item: ProcessingWorkItem,
        kind: ProcessingFailureKind,
        message: str,
        retryable: bool,
        object_ids: tuple[str, ...] = (),
        source_spans: tuple[SourceSpan, ...] = (),
        evidence: Metadata = (),
    ) -> ProcessingFailure:
        failure_id = stable_id(
            "processing-failure",
            work_item.work_item_id,
            kind.value,
            message,
            retryable,
            object_ids,
            tuple(_span_parts(span) for span in source_spans),
            evidence,
        )
        return cls(
            failure_id=failure_id,
            work_item_id=work_item.work_item_id,
            kind=kind,
            message=message,
            retryable=retryable,
            object_ids=object_ids,
            source_spans=source_spans,
            evidence=evidence,
        )

    def __post_init__(self) -> None:
        if self.contract_version != PROCESSING_CONTRACT_VERSION:
            raise ValueError("unsupported processing failure version")
        _identity_fields(self.work_item_id)
        if not isinstance(self.kind, ProcessingFailureKind):
            raise TypeError("processing failure kind is unsupported")
        _bounded_string(
            "processing failure message",
            self.message,
            nonempty=True,
            limit=_MAX_MESSAGE_CHARACTERS,
        )
        if not isinstance(self.retryable, bool):
            raise TypeError("processing failure retryable must be a boolean")
        _unique_strings("failure object IDs", self.object_ids)
        _validate_span_tuple("failure source spans", self.source_spans)
        _validate_metadata(self.evidence)
        expected = stable_id(
            "processing-failure",
            self.work_item_id,
            self.kind.value,
            self.message,
            self.retryable,
            self.object_ids,
            tuple(_span_parts(span) for span in self.source_spans),
            self.evidence,
        )
        if self.failure_id != expected:
            raise ValueError("processing failure ID is inconsistent")


class ProcessingProcessorError(RuntimeError):
    """Typed exception converted to selection-local failure evidence."""

    def __init__(
        self,
        *,
        kind: ProcessingFailureKind,
        message: str,
        retryable: bool,
        evidence: Metadata = (),
    ) -> None:
        if not isinstance(kind, ProcessingFailureKind):
            raise TypeError("processor error kind is unsupported")
        _bounded_string(
            "processor error message",
            message,
            nonempty=True,
            limit=_MAX_MESSAGE_CHARACTERS,
        )
        if not isinstance(retryable, bool):
            raise TypeError("processor error retryable must be a boolean")
        _validate_metadata(evidence)
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.retryable = retryable
        self.evidence = evidence


@dataclass(frozen=True)
class ProcessingInvocationResult:
    invocation_id: str
    work_item_id: str
    processor_identity_digest: str
    status: ProcessingStatus
    artifacts: tuple[ProcessingDerivedArtifact, ...]
    warnings: tuple[ProcessingWarning, ...]
    failures: tuple[ProcessingFailure, ...]
    contract_version: str = PROCESSING_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        work_item: ProcessingWorkItem,
        processor_identity: ProcessingProcessorIdentity,
        status: ProcessingStatus,
        artifacts: tuple[ProcessingDerivedArtifact, ...] = (),
        warnings: tuple[ProcessingWarning, ...] = (),
        failures: tuple[ProcessingFailure, ...] = (),
    ) -> ProcessingInvocationResult:
        invocation_id = _invocation_id(
            work_item.work_item_id,
            processor_identity.identity_digest,
            status,
            artifacts,
            warnings,
            failures,
        )
        return cls(
            invocation_id=invocation_id,
            work_item_id=work_item.work_item_id,
            processor_identity_digest=processor_identity.identity_digest,
            status=status,
            artifacts=artifacts,
            warnings=warnings,
            failures=failures,
        )

    def __post_init__(self) -> None:
        if self.contract_version != PROCESSING_CONTRACT_VERSION:
            raise ValueError("unsupported processing invocation version")
        _identity_fields(self.work_item_id, self.processor_identity_digest)
        if not isinstance(self.status, ProcessingStatus):
            raise TypeError("processing status is unsupported")
        _require_tuple("processing artifacts", self.artifacts)
        _require_tuple("processing warnings", self.warnings)
        _require_tuple("processing failures", self.failures)
        if (
            any(
                not isinstance(item, ProcessingDerivedArtifact)
                for item in self.artifacts
            )
            or any(
                not isinstance(item, ProcessingWarning)
                for item in self.warnings
            )
            or any(
                not isinstance(item, ProcessingFailure)
                for item in self.failures
            )
        ):
            raise TypeError(
                "processing invocation contains an unsupported value"
            )
        if len(self.artifacts) > _MAX_ARTIFACTS_PER_SELECTION:
            raise ProcessingLimitError("too many processing artifacts")
        if len(self.warnings) > _MAX_WARNINGS_PER_ATTEMPT:
            raise ProcessingLimitError("too many processing warnings")
        if len(self.failures) > _MAX_FAILURES_PER_ATTEMPT:
            raise ProcessingLimitError("too many processing failures")
        _unique_ids(
            "artifact", tuple(item.artifact_id for item in self.artifacts)
        )
        _unique_ids("warning", tuple(item.warning_id for item in self.warnings))
        _unique_ids("failure", tuple(item.failure_id for item in self.failures))
        if any(
            item.work_item_id != self.work_item_id for item in self.artifacts
        ):
            raise ValueError("artifact work-item identity is inconsistent")
        if any(
            item.work_item_id != self.work_item_id for item in self.warnings
        ):
            raise ValueError("warning work-item identity is inconsistent")
        if any(
            item.work_item_id != self.work_item_id for item in self.failures
        ):
            raise ValueError("failure work-item identity is inconsistent")
        if self.status is ProcessingStatus.COMPLETED:
            if self.failures:
                raise ValueError("completed processing cannot contain failures")
        elif self.status is ProcessingStatus.PARTIAL:
            if not self.artifacts or not self.failures:
                raise ValueError(
                    "partial processing requires artifacts and failures"
                )
        elif self.artifacts or not self.failures:
            raise ValueError(
                "failed processing requires failures without artifacts"
            )
        expected = _invocation_id(
            self.work_item_id,
            self.processor_identity_digest,
            self.status,
            self.artifacts,
            self.warnings,
            self.failures,
        )
        if self.invocation_id != expected:
            raise ValueError("processing invocation ID is inconsistent")


@dataclass(frozen=True)
class ProcessingAttempt:
    attempt_id: str
    attempt_number: int
    invocation: ProcessingInvocationResult
    contract_version: str = PROCESSING_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        attempt_number: int,
        invocation: ProcessingInvocationResult,
    ) -> ProcessingAttempt:
        return cls(
            attempt_id=stable_id(
                "processing-attempt",
                attempt_number,
                invocation.invocation_id,
            ),
            attempt_number=attempt_number,
            invocation=invocation,
        )

    def __post_init__(self) -> None:
        if self.contract_version != PROCESSING_CONTRACT_VERSION:
            raise ValueError("unsupported processing attempt version")
        _positive_integer("attempt_number", self.attempt_number)
        if not isinstance(self.invocation, ProcessingInvocationResult):
            raise TypeError("attempt invocation is unsupported")
        expected = stable_id(
            "processing-attempt",
            self.attempt_number,
            self.invocation.invocation_id,
        )
        if self.attempt_id != expected:
            raise ValueError("processing attempt ID is inconsistent")


@dataclass(frozen=True)
class ProcessingSelectionResult:
    selection_result_id: str
    selection_id: str
    work_item: ProcessingWorkItem
    processor_identity: ProcessingProcessorIdentity
    cache_key: str
    attempts: tuple[ProcessingAttempt, ...]
    retry_exhausted: bool
    contract_version: str = PROCESSING_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        work_item: ProcessingWorkItem,
        processor_identity: ProcessingProcessorIdentity,
        cache_key: str,
        attempts: tuple[ProcessingAttempt, ...],
        retry_exhausted: bool,
    ) -> ProcessingSelectionResult:
        selection_result_id = _selection_result_id(
            work_item,
            processor_identity,
            cache_key,
            attempts,
            retry_exhausted,
        )
        return cls(
            selection_result_id=selection_result_id,
            selection_id=work_item.selection_id,
            work_item=work_item,
            processor_identity=processor_identity,
            cache_key=cache_key,
            attempts=attempts,
            retry_exhausted=retry_exhausted,
        )

    def __post_init__(self) -> None:
        if self.contract_version != PROCESSING_CONTRACT_VERSION:
            raise ValueError("unsupported processing selection-result version")
        if not isinstance(self.work_item, ProcessingWorkItem):
            raise TypeError("selection result work item is unsupported")
        if self.selection_id != self.work_item.selection_id:
            raise ValueError("selection result identity is inconsistent")
        if not isinstance(self.processor_identity, ProcessingProcessorIdentity):
            raise TypeError("selection processor identity is unsupported")
        _identity_fields(self.cache_key)
        _require_tuple("processing attempts", self.attempts)
        if not self.attempts:
            raise ValueError("selection result requires an attempt")
        if len(self.attempts) > _MAX_ATTEMPTS:
            raise ProcessingLimitError("too many processing attempts")
        if any(
            not isinstance(item, ProcessingAttempt) for item in self.attempts
        ):
            raise TypeError("attempts contain an unsupported value")
        if tuple(item.attempt_number for item in self.attempts) != tuple(
            range(1, len(self.attempts) + 1)
        ):
            raise ValueError(
                "processing attempts must be consecutively ordered"
            )
        if any(
            item.invocation.work_item_id != self.work_item.work_item_id
            or item.invocation.processor_identity_digest
            != self.processor_identity.identity_digest
            for item in self.attempts
        ):
            raise ValueError("processing attempt identity is inconsistent")
        if any(
            item.invocation.status is not ProcessingStatus.FAILED
            for item in self.attempts[:-1]
        ):
            raise ValueError("only failed processing attempts may be retried")
        if any(
            not item.invocation.failures
            or not all(
                failure.retryable for failure in item.invocation.failures
            )
            for item in self.attempts[:-1]
        ):
            raise ValueError("retried attempts require retryable failures")
        if not isinstance(self.retry_exhausted, bool):
            raise TypeError("retry_exhausted must be a boolean")
        final = self.attempts[-1].invocation
        if self.retry_exhausted and (
            final.status is not ProcessingStatus.FAILED
            or not final.failures
            or not all(failure.retryable for failure in final.failures)
        ):
            raise ValueError(
                "retry exhaustion requires a retryable failed final attempt"
            )
        expected = _selection_result_id(
            self.work_item,
            self.processor_identity,
            self.cache_key,
            self.attempts,
            self.retry_exhausted,
        )
        if self.selection_result_id != expected:
            raise ValueError("processing selection-result ID is inconsistent")

    @property
    def final_invocation(self) -> ProcessingInvocationResult:
        return self.attempts[-1].invocation

    @property
    def status(self) -> ProcessingStatus:
        return self.final_invocation.status

    @property
    def artifacts(self) -> tuple[ProcessingDerivedArtifact, ...]:
        return self.final_invocation.artifacts


@dataclass(frozen=True)
class ProcessingRequest:
    request_id: str
    selections: tuple[ProcessingSelection, ...]
    work_items: tuple[ProcessingWorkItem, ...]
    configuration: ProcessingConfiguration
    contract_version: str = PROCESSING_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        selections: tuple[ProcessingSelection, ...],
        configuration: ProcessingConfiguration | None = None,
    ) -> ProcessingRequest:
        actual = configuration or ProcessingConfiguration()
        work_items = _build_work_items(selections, actual)
        return cls(
            request_id=_request_id(selections, work_items, actual),
            selections=selections,
            work_items=work_items,
            configuration=actual,
        )

    @classmethod
    def from_iterable(
        cls,
        *,
        selections: Iterable[ProcessingSelection],
        configuration: ProcessingConfiguration | None = None,
    ) -> ProcessingRequest:
        actual = configuration or ProcessingConfiguration()
        bounded = _bounded_iterable(
            selections,
            limit=actual.max_selections,
            name="processing selections",
        )
        return cls.create(selections=bounded, configuration=actual)

    def __post_init__(self) -> None:
        if self.contract_version != PROCESSING_CONTRACT_VERSION:
            raise ValueError("unsupported processing request version")
        if not isinstance(self.configuration, ProcessingConfiguration):
            raise TypeError("request configuration is unsupported")
        expected_work_items = _build_work_items(
            self.selections, self.configuration
        )
        if self.work_items != expected_work_items:
            raise ValueError("request work items are inconsistent")
        expected = _request_id(
            self.selections, self.work_items, self.configuration
        )
        if self.request_id != expected:
            raise ValueError("processing request ID is inconsistent")


@dataclass(frozen=True)
class ProcessingResult:
    result_id: str
    request: ProcessingRequest
    selection_results: tuple[ProcessingSelectionResult, ...]
    status: ProcessingStatus
    contract_version: str = PROCESSING_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        request: ProcessingRequest,
        selection_results: tuple[ProcessingSelectionResult, ...],
    ) -> ProcessingResult:
        status = _aggregate_status(selection_results)
        return cls(
            result_id=_processing_result_id(
                request.request_id, selection_results, status
            ),
            request=request,
            selection_results=selection_results,
            status=status,
        )

    def __post_init__(self) -> None:
        if self.contract_version != PROCESSING_CONTRACT_VERSION:
            raise ValueError("unsupported processing result version")
        if not isinstance(self.request, ProcessingRequest):
            raise TypeError("processing result request is unsupported")
        _require_tuple("selection results", self.selection_results)
        if any(
            not isinstance(item, ProcessingSelectionResult)
            for item in self.selection_results
        ):
            raise TypeError("selection results contain an unsupported value")
        if tuple(item.selection_id for item in self.selection_results) != tuple(
            item.selection_id for item in self.request.selections
        ):
            raise ValueError(
                "selection result order or coverage is inconsistent"
            )
        if tuple(
            item.work_item.work_item_id for item in self.selection_results
        ) != tuple(item.work_item_id for item in self.request.work_items):
            raise ValueError("selection work-item coverage is inconsistent")
        if not isinstance(self.status, ProcessingStatus):
            raise TypeError("processing result status is unsupported")
        if self.status is not _aggregate_status(self.selection_results):
            raise ValueError("processing aggregate status is inconsistent")
        _validate_configured_result(self)
        expected = _processing_result_id(
            self.request.request_id,
            self.selection_results,
            self.status,
        )
        if self.result_id != expected:
            raise ValueError("processing result ID is inconsistent")

    @property
    def cache_keys(self) -> tuple[str, ...]:
        return tuple(item.cache_key for item in self.selection_results)


class BoundedProcessingCoordinator:
    """Coordinate one injected processor over exact bounded selections."""

    name = "bounded-processing-coordinator"
    version = PROCESSING_COORDINATOR_VERSION

    def __init__(
        self,
        processor: ProcessingProcessor,
        *,
        cache: DerivedProcessingCache | None = None,
    ) -> None:
        self.processor = processor
        self.cache = cache

    def process(self, request: ProcessingRequest) -> ProcessingResult:
        if not isinstance(request, ProcessingRequest):
            raise TypeError("request must be ProcessingRequest")
        selection_results: list[ProcessingSelectionResult] = []
        retained_artifact_bytes = 0
        for work_item in request.work_items:
            selection_result = self._process_work_item(
                work_item, request.configuration
            )
            artifact_bytes = sum(
                artifact.byte_length for artifact in selection_result.artifacts
            )
            if retained_artifact_bytes + artifact_bytes > (
                request.configuration.max_total_artifact_bytes
            ):
                selection_result = _resource_limit_selection_result(
                    work_item,
                    selection_result.processor_identity,
                    selection_result.cache_key,
                    request.configuration,
                )
            else:
                retained_artifact_bytes += artifact_bytes
            if (
                self.cache is not None
                and selection_result.status is not ProcessingStatus.FAILED
            ):
                self.cache.put(selection_result.cache_key, selection_result)
            selection_results.append(selection_result)
        return ProcessingResult.create(
            request=request,
            selection_results=tuple(selection_results),
        )

    def _process_work_item(
        self,
        work_item: ProcessingWorkItem,
        configuration: ProcessingConfiguration,
    ) -> ProcessingSelectionResult:
        identity = self._processor_identity(work_item, configuration)
        cache_key = build_derived_processing_cache_key(
            work_item,
            identity,
            configuration,
        )
        if self.cache is not None:
            cached = self.cache.get(cache_key)
            if cached is not None:
                _validate_cached_selection_result(
                    cached,
                    work_item,
                    identity,
                    cache_key,
                    configuration,
                )
                return cached
        attempts: list[ProcessingAttempt] = []
        while len(attempts) < configuration.max_attempts_per_selection:
            invocation = self._invoke(work_item, identity, configuration)
            attempts.append(
                ProcessingAttempt.create(
                    attempt_number=len(attempts) + 1,
                    invocation=invocation,
                )
            )
            if not _invocation_is_retryable_failure(invocation):
                break
        final = attempts[-1].invocation
        retry_exhausted = (
            len(attempts) == configuration.max_attempts_per_selection
            and _invocation_is_retryable_failure(final)
        )
        result = ProcessingSelectionResult.create(
            work_item=work_item,
            processor_identity=identity,
            cache_key=cache_key,
            attempts=tuple(attempts),
            retry_exhausted=retry_exhausted,
        )
        _validate_configured_selection_result(result, configuration)
        return result

    def _processor_identity(
        self,
        work_item: ProcessingWorkItem,
        configuration: ProcessingConfiguration,
    ) -> ProcessingProcessorIdentity:
        try:
            identity = self.processor.identity_for(work_item)
        except Exception as error:
            raise ProcessingCoordinatorError(
                "processing processor identity resolution failed"
            ) from error
        if not isinstance(identity, ProcessingProcessorIdentity):
            raise ProcessingCoordinatorError(
                "processing processor returned an invalid identity"
            )
        if identity.processor_name != self.processor.name or (
            identity.processor_version != self.processor.version
        ):
            raise ProcessingCoordinatorError(
                "processing processor identity does not match its declaration"
            )
        if len(identity.resources) > configuration.max_resources:
            raise ProcessingLimitError("resources exceed max_resources")
        return identity

    def _invoke(
        self,
        work_item: ProcessingWorkItem,
        identity: ProcessingProcessorIdentity,
        configuration: ProcessingConfiguration,
    ) -> ProcessingInvocationResult:
        try:
            invocation = self.processor.process(work_item)
        except ProcessingProcessorError as error:
            return _failed_invocation(
                work_item,
                identity,
                configuration,
                kind=error.kind,
                message=error.message,
                retryable=error.retryable,
                evidence=error.evidence,
            )
        except ProcessingLimitError:
            return _failed_invocation(
                work_item,
                identity,
                configuration,
                kind=ProcessingFailureKind.RESOURCE_LIMIT,
                message="processor exceeded a bounded resource limit",
                retryable=False,
            )
        except Exception as error:
            return _failed_invocation(
                work_item,
                identity,
                configuration,
                kind=ProcessingFailureKind.PROCESSOR_ERROR,
                message=(
                    f"processor raised an unexpected {type(error).__name__}"
                ),
                retryable=False,
            )
        if not isinstance(invocation, ProcessingInvocationResult):
            return _failed_invocation(
                work_item,
                identity,
                configuration,
                kind=ProcessingFailureKind.OUTPUT_INVALID,
                message="processor returned an unsupported result",
                retryable=False,
            )
        if invocation.work_item_id != work_item.work_item_id or (
            invocation.processor_identity_digest != identity.identity_digest
        ):
            return _failed_invocation(
                work_item,
                identity,
                configuration,
                kind=ProcessingFailureKind.STALE_INPUT,
                message="processor result identity does not match the request",
                retryable=False,
            )
        try:
            _validate_invocation_against_work_item(invocation, work_item)
        except (TypeError, ValueError):
            return _failed_invocation(
                work_item,
                identity,
                configuration,
                kind=ProcessingFailureKind.OUTPUT_INVALID,
                message="processor result provenance is invalid",
                retryable=False,
            )
        try:
            _validate_configured_invocation(invocation, configuration)
        except ProcessingLimitError:
            return _failed_invocation(
                work_item,
                identity,
                configuration,
                kind=ProcessingFailureKind.RESOURCE_LIMIT,
                message="processor result exceeds configured resource limits",
                retryable=False,
            )
        return invocation


def build_derived_processing_cache_key(
    work_item: ProcessingWorkItem,
    processor_identity: ProcessingProcessorIdentity,
    configuration: ProcessingConfiguration,
) -> str:
    if not isinstance(work_item, ProcessingWorkItem):
        raise TypeError("work_item must be ProcessingWorkItem")
    if not isinstance(processor_identity, ProcessingProcessorIdentity):
        raise TypeError(
            "processor_identity must be ProcessingProcessorIdentity"
        )
    if not isinstance(configuration, ProcessingConfiguration):
        raise TypeError("configuration must be ProcessingConfiguration")
    if len(processor_identity.resources) > configuration.max_resources:
        raise ProcessingLimitError("resources exceed max_resources")
    return stable_id(
        "derived-processing-cache",
        PROCESSING_CONTRACT_VERSION,
        PROCESSING_COORDINATOR_VERSION,
        work_item.work_item_id,
        processor_identity.identity_parts(),
        configuration.identity_parts(),
    )


def _resolve_selection_evidence(
    document: ExtractedDocument,
    source_spans: tuple[SourceSpan, ...],
    physical_page_ranges: tuple[ProcessingPhysicalPageRange, ...],
    printed_page_ranges: tuple[ProcessingPrintedPageRange, ...],
    structure_analysis: StructureAnalysis | None,
    structure_node_ids: tuple[str, ...],
) -> _ResolvedSelectionEvidence:
    if not isinstance(document, ExtractedDocument):
        raise TypeError("selection document must be ExtractedDocument")
    if document.document_id != stable_id("document", document.source.source_id):
        raise ValueError("selection document identity is stale")
    _validate_span_tuple("selection source spans", source_spans)
    _require_tuple("physical page ranges", physical_page_ranges)
    _require_tuple("printed page ranges", printed_page_ranges)
    _unique_strings("structure node IDs", structure_node_ids)
    if len(source_spans) > _MAX_SOURCE_SPANS:
        raise ProcessingLimitError("too many selection source spans")
    if len(physical_page_ranges) + len(printed_page_ranges) > _MAX_PAGE_RANGES:
        raise ProcessingLimitError("too many selection page ranges")
    if len(structure_node_ids) > _MAX_STRUCTURE_NODES:
        raise ProcessingLimitError("too many selection structure nodes")
    if any(
        not isinstance(item, ProcessingPhysicalPageRange)
        for item in physical_page_ranges
    ):
        raise TypeError("physical page ranges contain an unsupported value")
    if any(
        not isinstance(item, ProcessingPrintedPageRange)
        for item in printed_page_ranges
    ):
        raise TypeError("printed page ranges contain an unsupported value")
    if not (
        source_spans
        or physical_page_ranges
        or printed_page_ranges
        or structure_node_ids
    ):
        raise ValueError("processing selection requires source evidence")
    page_by_index = {page.page_index: page for page in document.pages}
    for span in source_spans:
        _validate_span_against_document(span, document, page_by_index)
    selected_indices: set[int] = set()
    for page_range in physical_page_ranges:
        range_length = (
            page_range.end_page_index - page_range.start_page_index + 1
        )
        if range_length > _MAX_SELECTED_PAGES:
            raise ProcessingLimitError("physical page range is too large")
        requested = tuple(
            range(page_range.start_page_index, page_range.end_page_index + 1)
        )
        missing = tuple(
            index for index in requested if index not in page_by_index
        )
        if missing:
            raise ValueError("physical page range refers to a missing page")
        selected_indices.update(requested)
        if len(selected_indices) > _MAX_SELECTED_PAGES:
            raise ProcessingLimitError("too many selected pages")
    labels: dict[str, list[int]] = {}
    for page in document.pages:
        if page.printed_page_label is not None:
            labels.setdefault(page.printed_page_label, []).append(
                page.page_index
            )
    for printed_range in printed_page_ranges:
        starts = labels.get(printed_range.start_printed_page_label, [])
        ends = labels.get(printed_range.end_printed_page_label, [])
        if len(starts) != 1 or len(ends) != 1:
            raise ValueError(
                "printed page range endpoints must resolve uniquely"
            )
        start, end = starts[0], ends[0]
        if end < start:
            raise ValueError("printed page range must follow source page order")
        if end - start + 1 > _MAX_SELECTED_PAGES:
            raise ProcessingLimitError("printed page range is too large")
        requested = tuple(range(start, end + 1))
        if any(index not in page_by_index for index in requested):
            raise ValueError("printed page range crosses a missing page")
        selected_indices.update(requested)
        if len(selected_indices) > _MAX_SELECTED_PAGES:
            raise ProcessingLimitError("too many selected pages")
    selected_nodes: tuple[StructureNode, ...] = ()
    if structure_node_ids:
        if not isinstance(structure_analysis, StructureAnalysis):
            raise ValueError(
                "structure node selection requires a structure analysis"
            )
        if structure_analysis.source_id != document.source.source_id or (
            structure_analysis.source_blob_id != document.source.blob_id
        ):
            raise ValueError(
                "structure analysis must refer to the exact document source"
            )
        node_by_id = {node.node_id: node for node in structure_analysis.nodes}
        try:
            selected_nodes = tuple(
                node_by_id[node_id] for node_id in structure_node_ids
            )
        except KeyError as error:
            raise ValueError("structure node selection is stale") from error
        document_block_ids = {
            block.block_id for page in document.pages for block in page.blocks
        }
        for node in selected_nodes:
            for span in node.source_spans:
                _validate_span_against_document(span, document, page_by_index)
            if not set(node.source_block_ids).issubset(document_block_ids):
                raise ValueError("structure node source blocks are stale")
    elif structure_analysis is not None:
        raise ValueError(
            "structure analysis is only valid with structure node IDs"
        )
    return _ResolvedSelectionEvidence(
        selected_pages=tuple(
            page_by_index[index] for index in sorted(selected_indices)
        ),
        selected_nodes=selected_nodes,
    )


def _validate_span_against_document(
    span: SourceSpan,
    document: ExtractedDocument,
    page_by_index: dict[int, ExtractedPage],
) -> None:
    if span.source_id != document.source.source_id or (
        span.source_blob_id != document.source.blob_id
    ):
        raise ValueError("selection span must refer to the exact source")
    page = page_by_index.get(span.page_index)
    if page is None:
        raise ValueError("selection span refers to a missing page")
    if span.printed_page_label is not None and (
        span.printed_page_label != page.printed_page_label
    ):
        raise ValueError("selection span printed page label is stale")
    if span.bounding_box is not None:
        x0, y0, x1, y1 = span.bounding_box
        if any(not math.isfinite(value) for value in span.bounding_box):
            raise ValueError("selection span geometry must be finite")
        if x0 < 0 or y0 < 0 or x1 > page.width or y1 > page.height:
            raise ValueError("selection span geometry exceeds its source page")
    if span.source_object_id is not None:
        known_object_ids = {block.block_id for block in page.blocks} | {
            source_span.source_object_id
            for block in page.blocks
            for source_span in block.source_spans
            if source_span.source_object_id is not None
        }
        if span.source_object_id not in known_object_ids:
            raise ValueError("selection span source object is stale")
    if span.source_object_id is not None and span.start_offset is not None:
        block = next(
            (
                item
                for item in page.blocks
                if item.block_id == span.source_object_id
                or any(
                    source_span.source_object_id == span.source_object_id
                    for source_span in item.source_spans
                )
            ),
            None,
        )
        if block is not None and (
            block.text is None
            or span.end_offset is None
            or span.end_offset > len(block.text)
        ):
            raise ValueError("selection span offsets exceed source text")


def _selection_id(
    document: ExtractedDocument,
    source_spans: tuple[SourceSpan, ...],
    physical_page_ranges: tuple[ProcessingPhysicalPageRange, ...],
    printed_page_ranges: tuple[ProcessingPrintedPageRange, ...],
    selected_pages: tuple[ExtractedPage, ...],
    structure_analysis: StructureAnalysis | None,
    selected_nodes: tuple[StructureNode, ...],
) -> str:
    return stable_id(
        "processing-selection",
        PROCESSING_CONTRACT_VERSION,
        document.document_id,
        document.source.source_id,
        document.source.blob_id,
        tuple(_span_parts(span) for span in source_spans),
        tuple(item.range_id for item in physical_page_ranges),
        tuple(item.range_id for item in printed_page_ranges),
        selected_pages,
        structure_analysis.analysis_id
        if structure_analysis is not None
        else None,
        selected_nodes,
    )


def _build_work_items(
    selections: tuple[ProcessingSelection, ...],
    configuration: ProcessingConfiguration,
) -> tuple[ProcessingWorkItem, ...]:
    _require_tuple("processing selections", selections)
    if not selections:
        raise ValueError("processing request requires a selection")
    if len(selections) > configuration.max_selections:
        raise ProcessingLimitError("selections exceed max_selections")
    if any(not isinstance(item, ProcessingSelection) for item in selections):
        raise TypeError("processing selections contain an unsupported value")
    selection_ids = tuple(item.selection_id for item in selections)
    if len(set(selection_ids)) != len(selection_ids):
        raise ValueError("processing selections must be unique")
    work_items = tuple(
        _build_work_item(selection, configuration) for selection in selections
    )
    _validate_retained_size(
        (selections, work_items, configuration), configuration.max_result_bytes
    )
    return work_items


def _build_work_item(
    selection: ProcessingSelection,
    configuration: ProcessingConfiguration,
) -> ProcessingWorkItem:
    evidence = _resolve_selection_evidence(
        selection.document,
        selection.source_spans,
        selection.physical_page_ranges,
        selection.printed_page_ranges,
        selection.structure_analysis,
        selection.structure_node_ids,
    )
    if (
        len(selection.physical_page_ranges) + len(selection.printed_page_ranges)
        > configuration.max_page_ranges_per_selection
    ):
        raise ProcessingLimitError(
            "page ranges exceed max_page_ranges_per_selection"
        )
    if (
        len(evidence.selected_pages)
        > configuration.max_selected_pages_per_selection
    ):
        raise ProcessingLimitError(
            "selected pages exceed max_selected_pages_per_selection"
        )
    if (
        len(evidence.selected_nodes)
        > configuration.max_structure_nodes_per_selection
    ):
        raise ProcessingLimitError(
            "structure nodes exceed max_structure_nodes_per_selection"
        )
    if (
        len(selection.source_spans)
        > configuration.max_source_spans_per_selection
    ):
        raise ProcessingLimitError(
            "source spans exceed max_source_spans_per_selection"
        )
    spans = _deduplicate_spans(
        selection.source_spans
        + tuple(
            span
            for page in evidence.selected_pages
            for block in page.blocks
            for span in block.source_spans
        )
        + tuple(
            span
            for node in evidence.selected_nodes
            for span in node.source_spans
        )
    )
    object_ids = _deduplicate_strings(
        tuple(
            _selected_page_object_id(selection.document.source, page)
            for page in evidence.selected_pages
        )
        + tuple(
            block.block_id
            for page in evidence.selected_pages
            for block in page.blocks
        )
        + tuple(
            span.source_object_id
            for span in selection.source_spans
            if span.source_object_id is not None
        )
        + tuple(node.node_id for node in evidence.selected_nodes)
        + tuple(
            block_id
            for node in evidence.selected_nodes
            for block_id in node.source_block_ids
        )
    )
    if len(spans) > configuration.max_source_spans_per_selection:
        raise ProcessingLimitError(
            "resolved source spans exceed max_source_spans_per_selection"
        )
    if len(object_ids) > configuration.max_input_object_ids_per_selection:
        raise ProcessingLimitError(
            "input object IDs exceed max_input_object_ids_per_selection"
        )
    work_item_id = _work_item_id(
        selection.selection_id,
        selection.document.source,
        evidence.selected_pages,
        spans,
        evidence.selected_nodes,
        object_ids,
    )
    return ProcessingWorkItem(
        work_item_id=work_item_id,
        selection_id=selection.selection_id,
        source=selection.document.source,
        full_pages=evidence.selected_pages,
        source_spans=spans,
        structure_nodes=evidence.selected_nodes,
        input_object_ids=object_ids,
    )


def _selected_page_object_id(
    source: SourceDocument, page: ExtractedPage
) -> str:
    return stable_id(
        "processing-selected-page",
        source.source_id,
        source.blob_id,
        page,
    )


def _work_item_id(
    selection_id: str,
    source: SourceDocument,
    full_pages: tuple[ExtractedPage, ...],
    source_spans: tuple[SourceSpan, ...],
    structure_nodes: tuple[StructureNode, ...],
    input_object_ids: tuple[str, ...],
) -> str:
    return stable_id(
        "processing-work-item",
        selection_id,
        source.source_id,
        source.blob_id,
        full_pages,
        tuple(_span_parts(span) for span in source_spans),
        structure_nodes,
        input_object_ids,
    )


def _request_id(
    selections: tuple[ProcessingSelection, ...],
    work_items: tuple[ProcessingWorkItem, ...],
    configuration: ProcessingConfiguration,
) -> str:
    return stable_id(
        "processing-request",
        PROCESSING_CONTRACT_VERSION,
        tuple(item.selection_id for item in selections),
        tuple(item.work_item_id for item in work_items),
        configuration.identity_parts(),
    )


def _invocation_id(
    work_item_id: str,
    processor_identity_digest: str,
    status: ProcessingStatus,
    artifacts: tuple[ProcessingDerivedArtifact, ...],
    warnings: tuple[ProcessingWarning, ...],
    failures: tuple[ProcessingFailure, ...],
) -> str:
    return stable_id(
        "processing-invocation",
        work_item_id,
        processor_identity_digest,
        status.value,
        tuple(item.artifact_id for item in artifacts),
        tuple(item.warning_id for item in warnings),
        tuple(item.failure_id for item in failures),
    )


def _selection_result_id(
    work_item: ProcessingWorkItem,
    processor_identity: ProcessingProcessorIdentity,
    cache_key: str,
    attempts: tuple[ProcessingAttempt, ...],
    retry_exhausted: bool,
) -> str:
    return stable_id(
        "processing-selection-result",
        work_item.selection_id,
        work_item.work_item_id,
        processor_identity.identity_parts(),
        cache_key,
        tuple(item.attempt_id for item in attempts),
        retry_exhausted,
    )


def _processing_result_id(
    request_id: str,
    selection_results: tuple[ProcessingSelectionResult, ...],
    status: ProcessingStatus,
) -> str:
    return stable_id(
        "processing-result",
        request_id,
        tuple(item.selection_result_id for item in selection_results),
        status.value,
    )


def _aggregate_status(
    selection_results: tuple[ProcessingSelectionResult, ...],
) -> ProcessingStatus:
    if not selection_results:
        raise ValueError("processing result requires selection results")
    statuses = tuple(item.status for item in selection_results)
    if all(status is ProcessingStatus.COMPLETED for status in statuses):
        return ProcessingStatus.COMPLETED
    if all(status is ProcessingStatus.FAILED for status in statuses):
        return ProcessingStatus.FAILED
    return ProcessingStatus.PARTIAL


def _failed_invocation(
    work_item: ProcessingWorkItem,
    processor_identity: ProcessingProcessorIdentity,
    configuration: ProcessingConfiguration,
    *,
    kind: ProcessingFailureKind,
    message: str,
    retryable: bool,
    evidence: Metadata = (),
) -> ProcessingInvocationResult:
    bounded_message = message[: configuration.max_message_characters]
    bounded_evidence = evidence
    if (
        len(evidence) > configuration.max_metadata_entries
        or sum(len(key) + len(value) for key, value in evidence)
        > configuration.max_metadata_characters
    ):
        bounded_evidence = ()
    failure = ProcessingFailure.create(
        work_item=work_item,
        kind=kind,
        message=bounded_message,
        retryable=retryable,
        evidence=bounded_evidence,
    )
    return ProcessingInvocationResult.create(
        work_item=work_item,
        processor_identity=processor_identity,
        status=ProcessingStatus.FAILED,
        failures=(failure,),
    )


def _resource_limit_selection_result(
    work_item: ProcessingWorkItem,
    processor_identity: ProcessingProcessorIdentity,
    cache_key: str,
    configuration: ProcessingConfiguration,
) -> ProcessingSelectionResult:
    invocation = _failed_invocation(
        work_item,
        processor_identity,
        configuration,
        kind=ProcessingFailureKind.RESOURCE_LIMIT,
        message="aggregate processing artifacts exceed configured limits",
        retryable=False,
    )
    return ProcessingSelectionResult.create(
        work_item=work_item,
        processor_identity=processor_identity,
        cache_key=cache_key,
        attempts=(
            ProcessingAttempt.create(
                attempt_number=1,
                invocation=invocation,
            ),
        ),
        retry_exhausted=False,
    )


def _invocation_is_retryable_failure(
    invocation: ProcessingInvocationResult,
) -> bool:
    return (
        invocation.status is ProcessingStatus.FAILED
        and bool(invocation.failures)
        and all(failure.retryable for failure in invocation.failures)
    )


def _validate_invocation_against_work_item(
    invocation: ProcessingInvocationResult,
    work_item: ProcessingWorkItem,
) -> None:
    for artifact in invocation.artifacts:
        _validate_output_references(
            artifact.input_object_ids,
            artifact.source_spans,
            work_item,
        )
    for warning in invocation.warnings:
        _validate_output_references(
            warning.object_ids,
            warning.source_spans,
            work_item,
        )
    for failure in invocation.failures:
        _validate_output_references(
            failure.object_ids,
            failure.source_spans,
            work_item,
        )


def _validate_output_references(
    object_ids: tuple[str, ...],
    source_spans: tuple[SourceSpan, ...],
    work_item: ProcessingWorkItem,
) -> None:
    if not set(object_ids).issubset(work_item.input_object_ids):
        raise ValueError("processing output references an unselected object")
    full_page_by_index = {
        page.page_index: page for page in work_item.full_pages
    }
    for span in source_spans:
        if span.source_id != work_item.source.source_id or (
            span.source_blob_id != work_item.source.blob_id
        ):
            raise ValueError("processing output references another source")
        if span.bounding_box is not None and any(
            not math.isfinite(value) for value in span.bounding_box
        ):
            raise ValueError("processing output geometry must be finite")
        full_page = full_page_by_index.get(span.page_index)
        if full_page is not None:
            _validate_span_against_page(span, full_page)
            continue
        if not any(
            _span_contains(parent, span) for parent in work_item.source_spans
        ):
            raise ValueError("processing output span exceeds its selection")


def _validate_span_against_page(span: SourceSpan, page: ExtractedPage) -> None:
    if span.printed_page_label is not None and (
        span.printed_page_label != page.printed_page_label
    ):
        raise ValueError("processing output printed page label is stale")
    if span.bounding_box is not None:
        x0, y0, x1, y1 = span.bounding_box
        if any(not math.isfinite(value) for value in span.bounding_box):
            raise ValueError("processing output geometry must be finite")
        if x0 < 0 or y0 < 0 or x1 > page.width or y1 > page.height:
            raise ValueError(
                "processing output geometry exceeds its source page"
            )


def _span_contains(parent: SourceSpan, child: SourceSpan) -> bool:
    if parent.source_id != child.source_id or (
        parent.source_blob_id != child.source_blob_id
        or parent.page_index != child.page_index
    ):
        return False
    if parent.printed_page_label is not None and (
        child.printed_page_label is not None
        and child.printed_page_label != parent.printed_page_label
    ):
        return False
    if parent.source_object_id is not None and (
        child.source_object_id != parent.source_object_id
    ):
        return False
    if parent.bounding_box is not None:
        if child.bounding_box is None:
            return False
        px0, py0, px1, py1 = parent.bounding_box
        cx0, cy0, cx1, cy1 = child.bounding_box
        if cx0 < px0 or cy0 < py0 or cx1 > px1 or cy1 > py1:
            return False
    if parent.start_offset is not None:
        if child.start_offset is None or child.end_offset is None:
            return False
        assert parent.end_offset is not None
        if (
            child.start_offset < parent.start_offset
            or child.end_offset > parent.end_offset
        ):
            return False
    return True


def _validate_cached_selection_result(
    result: ProcessingSelectionResult,
    work_item: ProcessingWorkItem,
    identity: ProcessingProcessorIdentity,
    cache_key: str,
    configuration: ProcessingConfiguration,
) -> None:
    if not isinstance(result, ProcessingSelectionResult):
        raise ProcessingCoordinatorError(
            "derived processing cache returned an unsupported value"
        )
    if result.work_item != work_item or result.processor_identity != identity:
        raise ProcessingCoordinatorError(
            "derived processing cache returned stale input"
        )
    if result.cache_key != cache_key:
        raise ProcessingCoordinatorError(
            "derived processing cache returned the wrong key"
        )
    if result.status is ProcessingStatus.FAILED:
        raise ProcessingCoordinatorError(
            "derived processing cache must not retain failed results"
        )
    _validate_configured_selection_result(result, configuration)


def _validate_configured_selection_result(
    result: ProcessingSelectionResult,
    configuration: ProcessingConfiguration,
) -> None:
    if len(result.attempts) > configuration.max_attempts_per_selection:
        raise ProcessingLimitError("attempts exceed max_attempts_per_selection")
    total_warnings = 0
    total_failures = 0
    for attempt in result.attempts:
        invocation = attempt.invocation
        _validate_invocation_against_work_item(invocation, result.work_item)
        _validate_configured_invocation(invocation, configuration)
        total_warnings += len(invocation.warnings)
        total_failures += len(invocation.failures)
    if total_warnings > configuration.max_total_warnings:
        raise ProcessingLimitError("warnings exceed max_total_warnings")
    if total_failures > configuration.max_total_failures:
        raise ProcessingLimitError("failures exceed max_total_failures")


def _validate_configured_invocation(
    invocation: ProcessingInvocationResult,
    configuration: ProcessingConfiguration,
) -> None:
    if len(invocation.warnings) > configuration.max_warnings_per_attempt:
        raise ProcessingLimitError("warnings exceed max_warnings_per_attempt")
    if len(invocation.failures) > configuration.max_failures_per_attempt:
        raise ProcessingLimitError("failures exceed max_failures_per_attempt")
    for warning in invocation.warnings:
        _validate_configured_message(
            warning.message,
            warning.evidence,
            configuration,
        )
        if warning.suggested_recovery is not None and (
            len(warning.suggested_recovery)
            > configuration.max_message_characters
        ):
            raise ProcessingLimitError(
                "suggested recovery exceeds configured limit"
            )
    for failure in invocation.failures:
        _validate_configured_message(
            failure.message,
            failure.evidence,
            configuration,
        )
    if len(invocation.artifacts) > configuration.max_artifacts_per_selection:
        raise ProcessingLimitError(
            "artifacts exceed max_artifacts_per_selection"
        )
    if any(
        artifact.byte_length > configuration.max_artifact_bytes
        for artifact in invocation.artifacts
    ):
        raise ProcessingLimitError("artifact exceeds max_artifact_bytes")
    if sum(artifact.byte_length for artifact in invocation.artifacts) > (
        configuration.max_total_artifact_bytes
    ):
        raise ProcessingLimitError("artifacts exceed max_total_artifact_bytes")


def _validate_configured_result(result: ProcessingResult) -> None:
    configuration = result.request.configuration
    for selection_result in result.selection_results:
        expected_key = build_derived_processing_cache_key(
            selection_result.work_item,
            selection_result.processor_identity,
            configuration,
        )
        if selection_result.cache_key != expected_key:
            raise ValueError("processing cache key is inconsistent")
        _validate_configured_selection_result(selection_result, configuration)
    total_warnings = sum(
        len(attempt.invocation.warnings)
        for selection_result in result.selection_results
        for attempt in selection_result.attempts
    )
    total_failures = sum(
        len(attempt.invocation.failures)
        for selection_result in result.selection_results
        for attempt in selection_result.attempts
    )
    if total_warnings > configuration.max_total_warnings:
        raise ProcessingLimitError("result warnings exceed max_total_warnings")
    if total_failures > configuration.max_total_failures:
        raise ProcessingLimitError("result failures exceed max_total_failures")
    total_bytes = sum(
        artifact.byte_length
        for selection_result in result.selection_results
        for artifact in selection_result.artifacts
    )
    if total_bytes > configuration.max_total_artifact_bytes:
        raise ProcessingLimitError(
            "result artifacts exceed max_total_artifact_bytes"
        )
    _validate_retained_size(result, configuration.max_result_bytes)


def _validate_configured_message(
    message: str,
    evidence: Metadata,
    configuration: ProcessingConfiguration,
) -> None:
    if len(message) > configuration.max_message_characters:
        raise ProcessingLimitError(
            "processing message exceeds configured limit"
        )
    if len(evidence) > configuration.max_metadata_entries:
        raise ProcessingLimitError("metadata exceeds max_metadata_entries")
    if sum(len(key) + len(value) for key, value in evidence) > (
        configuration.max_metadata_characters
    ):
        raise ProcessingLimitError("metadata exceeds max_metadata_characters")


def _span_parts(span: SourceSpan) -> tuple[object, ...]:
    return span.identity_parts() + (span.printed_page_label,)


def _deduplicate_spans(spans: tuple[SourceSpan, ...]) -> tuple[SourceSpan, ...]:
    result: list[SourceSpan] = []
    seen: set[tuple[object, ...]] = set()
    for span in spans:
        identity = _span_parts(span)
        if identity not in seen:
            seen.add(identity)
            result.append(span)
    return tuple(result)


def _deduplicate_strings(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _bounded_iterable(
    values: Iterable[ProcessingSelection],
    *,
    limit: int,
    name: str,
) -> tuple[ProcessingSelection, ...]:
    iterator = iter(values)
    result: list[ProcessingSelection] = []
    for _ in range(limit + 1):
        try:
            result.append(next(iterator))
        except StopIteration:
            return tuple(result)
    raise ProcessingLimitError(f"{name} exceed configured limit")


def _validate_span_tuple(name: str, spans: tuple[SourceSpan, ...]) -> None:
    _require_tuple(name, spans)
    if any(not isinstance(span, SourceSpan) for span in spans):
        raise TypeError(f"{name} contain an unsupported value")
    identities = tuple(_span_parts(span) for span in spans)
    if len(set(identities)) != len(identities):
        raise ValueError(f"{name} must be unique")


def _validate_metadata(value: Metadata) -> None:
    _require_tuple("metadata", value)
    if len(value) > _MAX_METADATA_ENTRIES:
        raise ProcessingLimitError("too many metadata entries")
    total = 0
    for entry in value:
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise TypeError("metadata must contain immutable pairs")
        key, item = entry
        _bounded_string("metadata key", key, nonempty=True)
        _bounded_string("metadata value", item)
        total += len(key) + len(item)
    if total > _MAX_METADATA_CHARACTERS:
        raise ProcessingLimitError("metadata exceeds its hard limit")


def _identity_fields(*values: str) -> None:
    for value in values:
        _bounded_string("identity field", value, nonempty=True)


def _unique_strings(name: str, values: tuple[str, ...]) -> None:
    _require_tuple(name, values)
    for value in values:
        _bounded_string(name, value, nonempty=True)
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must be unique")


def _unique_ids(name: str, values: tuple[str, ...]) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"processing {name} IDs must be unique")


def _require_tuple(name: str, value: object) -> None:
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be an immutable tuple")


def _bounded_string(
    name: str,
    value: object,
    *,
    nonempty: bool = False,
    limit: int = _MAX_IDENTITY_CHARACTERS,
) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if nonempty and not value:
        raise ValueError(f"{name} must be non-empty")
    if len(value) > limit:
        raise ProcessingLimitError(f"{name} exceeds its hard limit")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(f"{name} must be valid UTF-8") from error


def _positive_integer(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _nonnegative_integer(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _sha256(name: str, value: str) -> None:
    if len(value) != 64:
        raise ValueError(f"{name} must be a SHA-256 digest")
    try:
        int(value, 16)
    except ValueError as error:
        raise ValueError(f"{name} must be a SHA-256 digest") from error


def _bytes_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _validate_retained_size(value: object, limit: int) -> None:
    total = 0
    stack = [value]
    seen: set[int] = set()
    while stack:
        item = stack.pop()
        if item is None or isinstance(item, (bool, int, float, Enum)):
            total += 16
        elif isinstance(item, str):
            total += len(item.encode("utf-8")) + 8
        elif isinstance(item, bytes):
            total += len(item)
        elif isinstance(item, tuple):
            marker = id(item)
            if marker in seen:
                continue
            seen.add(marker)
            total += 8 * len(item)
            stack.extend(item)
        elif is_dataclass(item) and not isinstance(item, type):
            marker = id(item)
            if marker in seen:
                continue
            seen.add(marker)
            for field in fields(item):
                total += len(field.name) + 3
                if (
                    item.__class__.__name__ == "ProcessingDerivedArtifact"
                    and field.name == "content"
                ):
                    continue
                stack.append(getattr(item, field.name))
        else:
            raise TypeError("processing result contains unsupported evidence")
        if total > limit:
            raise ProcessingLimitError(
                "processing result exceeds max_result_bytes"
            )
