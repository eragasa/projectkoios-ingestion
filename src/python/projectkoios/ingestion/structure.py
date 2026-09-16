from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import (
    IngestionWarning,
    Metadata,
    SourceDocument,
    SourceSpan,
    WarningSeverity,
)

STRUCTURE_CONTRACT_VERSION = "1.0"
_MAX_NODES = 4_096
_MAX_WARNINGS = 4_096
_MAX_SOURCE_SPANS_PER_NODE = 2_048
_MAX_SOURCE_SPANS_PER_ANALYSIS = 16_384
_MAX_LINKS_PER_NODE = 4_096
_MAX_INPUT_BLOCK_IDS = 16_384
_MAX_IDENTITY_CHARACTERS = 4_096
_MAX_TEXT_CHARACTERS = 1_000_000
_MAX_ANALYSIS_TEXT_CHARACTERS = 5_000_000


class StructureKind(StrEnum):
    DOCUMENT = "document"
    FRONT_MATTER = "front_matter"
    TITLE = "title"
    AUTHOR = "author"
    ABSTRACT = "abstract"
    KEYWORDS = "keywords"
    PART = "part"
    CHAPTER = "chapter"
    SECTION = "section"
    SUBSECTION = "subsection"
    PROSE = "prose"
    EQUATION = "equation"
    FIGURE = "figure"
    TABLE = "table"
    EXAMPLE = "example"
    PROBLEM_SET = "problem_set"
    PROBLEM = "problem"
    APPENDIX = "appendix"
    BIBLIOGRAPHY = "bibliography"
    BIBLIOGRAPHY_ENTRY = "bibliography_entry"
    INDEX = "index"
    UNKNOWN = "unknown"


class StructureEvidenceStatus(StrEnum):
    """What a node asserts; intentionally has no accepted/validated state."""

    OBSERVED = "observed"
    PROPOSED = "proposed"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class StructureNode:
    node_id: str
    kind: StructureKind
    source_spans: tuple[SourceSpan, ...]
    evidence_type: str
    confidence: float
    label: str | None = None
    title: str | None = None
    parent_id: str | None = None
    child_ids: tuple[str, ...] = ()
    evidence: Metadata = ()
    warning_ids: tuple[str, ...] = ()
    source_block_ids: tuple[str, ...] = ()
    heading_level: int | None = None
    reading_order: int | None = None
    heading_confidence: float | None = None
    reading_order_confidence: float | None = None
    evidence_status: StructureEvidenceStatus = StructureEvidenceStatus.PROPOSED
    contract_version: str = STRUCTURE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        kind: StructureKind,
        source_spans: tuple[SourceSpan, ...],
        evidence_type: str,
        confidence: float,
        label: str | None = None,
        title: str | None = None,
        parent_id: str | None = None,
        child_ids: tuple[str, ...] = (),
        evidence: Metadata = (),
        warning_ids: tuple[str, ...] = (),
        source_block_ids: tuple[str, ...] = (),
        heading_level: int | None = None,
        reading_order: int | None = None,
        heading_confidence: float | None = None,
        reading_order_confidence: float | None = None,
        evidence_status: StructureEvidenceStatus = (
            StructureEvidenceStatus.PROPOSED
        ),
    ) -> StructureNode:
        normalized_confidence = _unit_float("confidence", confidence)
        normalized_heading_confidence = (
            _unit_float("heading_confidence", heading_confidence)
            if heading_confidence is not None
            else None
        )
        normalized_reading_confidence = (
            _unit_float("reading_order_confidence", reading_order_confidence)
            if reading_order_confidence is not None
            else None
        )
        _validate_node_parts(
            kind=kind,
            source_spans=source_spans,
            evidence_type=evidence_type,
            confidence=normalized_confidence,
            label=label,
            title=title,
            parent_id=parent_id,
            child_ids=child_ids,
            evidence=evidence,
            warning_ids=warning_ids,
            source_block_ids=source_block_ids,
            heading_level=heading_level,
            reading_order=reading_order,
            heading_confidence=normalized_heading_confidence,
            reading_order_confidence=normalized_reading_confidence,
            evidence_status=evidence_status,
        )
        node_id = _structure_node_id(
            kind=kind,
            source_spans=source_spans,
            evidence_type=evidence_type,
            confidence=normalized_confidence,
            label=label,
            title=title,
            evidence=evidence,
            source_block_ids=source_block_ids,
            heading_level=heading_level,
            heading_confidence=normalized_heading_confidence,
            evidence_status=evidence_status,
        )
        return cls(
            node_id=node_id,
            kind=kind,
            source_spans=source_spans,
            evidence_type=evidence_type,
            confidence=normalized_confidence,
            label=label,
            title=title,
            parent_id=parent_id,
            child_ids=child_ids,
            evidence=evidence,
            warning_ids=warning_ids,
            source_block_ids=source_block_ids,
            heading_level=heading_level,
            reading_order=reading_order,
            heading_confidence=normalized_heading_confidence,
            reading_order_confidence=normalized_reading_confidence,
            evidence_status=evidence_status,
        )

    def __post_init__(self) -> None:
        if self.contract_version != STRUCTURE_CONTRACT_VERSION:
            raise ValueError("unsupported structure node contract version")
        _bounded_string("node_id", self.node_id)
        object.__setattr__(
            self, "confidence", _unit_float("confidence", self.confidence)
        )
        if self.heading_confidence is not None:
            object.__setattr__(
                self,
                "heading_confidence",
                _unit_float("heading_confidence", self.heading_confidence),
            )
        if self.reading_order_confidence is not None:
            object.__setattr__(
                self,
                "reading_order_confidence",
                _unit_float(
                    "reading_order_confidence",
                    self.reading_order_confidence,
                ),
            )
        _validate_node_parts(
            kind=self.kind,
            source_spans=self.source_spans,
            evidence_type=self.evidence_type,
            confidence=self.confidence,
            label=self.label,
            title=self.title,
            parent_id=self.parent_id,
            child_ids=self.child_ids,
            evidence=self.evidence,
            warning_ids=self.warning_ids,
            source_block_ids=self.source_block_ids,
            heading_level=self.heading_level,
            reading_order=self.reading_order,
            heading_confidence=self.heading_confidence,
            reading_order_confidence=self.reading_order_confidence,
            evidence_status=self.evidence_status,
        )
        expected = _structure_node_id(
            kind=self.kind,
            source_spans=self.source_spans,
            evidence_type=self.evidence_type,
            confidence=self.confidence,
            label=self.label,
            title=self.title,
            evidence=self.evidence,
            source_block_ids=self.source_block_ids,
            heading_level=self.heading_level,
            heading_confidence=self.heading_confidence,
            evidence_status=self.evidence_status,
        )
        if self.node_id != expected:
            raise ValueError("structure node ID is inconsistent")


@dataclass(frozen=True)
class StructureAnalysis:
    nodes: tuple[StructureNode, ...]
    warnings: tuple[IngestionWarning, ...] = ()
    analysis_id: str | None = None
    source_id: str | None = None
    source_blob_id: str | None = None
    layout_result_ids: tuple[str, ...] = ()
    input_block_ids: tuple[str, ...] = ()
    processor_name: str | None = None
    processor_version: str | None = None
    configuration_digest: str | None = None
    contract_version: str = STRUCTURE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        source: SourceDocument,
        nodes: tuple[StructureNode, ...],
        warnings: tuple[IngestionWarning, ...],
        layout_result_ids: tuple[str, ...],
        input_block_ids: tuple[str, ...],
        processor_name: str,
        processor_version: str,
        configuration_digest: str,
    ) -> StructureAnalysis:
        if not isinstance(source, SourceDocument):
            raise TypeError("source must be SourceDocument")
        _validate_analysis_parts(
            nodes=nodes,
            warnings=warnings,
            source_id=source.source_id,
            source_blob_id=source.blob_id,
            layout_result_ids=layout_result_ids,
            input_block_ids=input_block_ids,
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=configuration_digest,
        )
        analysis_id = _structure_analysis_id(
            source_id=source.source_id,
            source_blob_id=source.blob_id,
            nodes=nodes,
            warnings=warnings,
            layout_result_ids=layout_result_ids,
            input_block_ids=input_block_ids,
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=configuration_digest,
        )
        return cls(
            nodes=nodes,
            warnings=warnings,
            analysis_id=analysis_id,
            source_id=source.source_id,
            source_blob_id=source.blob_id,
            layout_result_ids=layout_result_ids,
            input_block_ids=input_block_ids,
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=configuration_digest,
        )

    def __post_init__(self) -> None:
        if self.contract_version != STRUCTURE_CONTRACT_VERSION:
            raise ValueError("unsupported structure analysis contract version")
        context = (
            self.analysis_id,
            self.source_id,
            self.source_blob_id,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        )
        if any(value is not None for value in context) and not all(
            value is not None for value in context
        ):
            raise ValueError(
                "structure analysis identity context is incomplete"
            )
        if self.analysis_id is None and (
            self.layout_result_ids or self.input_block_ids
        ):
            raise ValueError(
                "input evidence IDs require complete analysis identity context"
            )
        _validate_analysis_parts(
            nodes=self.nodes,
            warnings=self.warnings,
            source_id=self.source_id,
            source_blob_id=self.source_blob_id,
            layout_result_ids=self.layout_result_ids,
            input_block_ids=self.input_block_ids,
            processor_name=self.processor_name,
            processor_version=self.processor_version,
            configuration_digest=self.configuration_digest,
        )
        if self.analysis_id is not None:
            _bounded_string("analysis_id", self.analysis_id)
            assert self.source_id is not None
            assert self.source_blob_id is not None
            assert self.processor_name is not None
            assert self.processor_version is not None
            assert self.configuration_digest is not None
            expected = _structure_analysis_id(
                source_id=self.source_id,
                source_blob_id=self.source_blob_id,
                nodes=self.nodes,
                warnings=self.warnings,
                layout_result_ids=self.layout_result_ids,
                input_block_ids=self.input_block_ids,
                processor_name=self.processor_name,
                processor_version=self.processor_version,
                configuration_digest=self.configuration_digest,
            )
            if self.analysis_id != expected:
                raise ValueError("structure analysis ID is inconsistent")


def _validate_node_parts(
    *,
    kind: StructureKind,
    source_spans: tuple[SourceSpan, ...],
    evidence_type: str,
    confidence: float,
    label: str | None,
    title: str | None,
    parent_id: str | None,
    child_ids: tuple[str, ...],
    evidence: Metadata,
    warning_ids: tuple[str, ...],
    source_block_ids: tuple[str, ...],
    heading_level: int | None,
    reading_order: int | None,
    heading_confidence: float | None,
    reading_order_confidence: float | None,
    evidence_status: StructureEvidenceStatus,
) -> None:
    if not isinstance(kind, StructureKind):
        raise TypeError("kind must be StructureKind")
    _require_tuple("source_spans", source_spans)
    if not source_spans:
        raise ValueError("a structure node must have source spans")
    if len(source_spans) > _MAX_SOURCE_SPANS_PER_NODE:
        raise ValueError("structure node has too many source spans")
    if any(not isinstance(span, SourceSpan) for span in source_spans):
        raise TypeError("source_spans must contain SourceSpan values")
    _bounded_string("evidence_type", evidence_type)
    _unit_float("confidence", confidence)
    for name, value in (("label", label), ("title", title)):
        if value is not None:
            _bounded_text(name, value, nonempty=True)
    if parent_id is not None:
        _bounded_string("parent_id", parent_id)
    _unique_strings("child_ids", child_ids)
    _unique_strings("warning_ids", warning_ids)
    _unique_strings("source_block_ids", source_block_ids)
    if len(child_ids) > _MAX_LINKS_PER_NODE:
        raise ValueError("structure node has too many children")
    _validate_metadata(evidence)
    _optional_nonnegative_integer("heading_level", heading_level)
    _optional_nonnegative_integer("reading_order", reading_order)
    if (heading_level is None) != (heading_confidence is None):
        raise ValueError(
            "heading level and heading confidence must be present together"
        )
    if (reading_order is None) != (reading_order_confidence is None):
        raise ValueError(
            "reading order and reading-order confidence must be present "
            "together"
        )
    if heading_confidence is not None:
        _unit_float("heading_confidence", heading_confidence)
    if reading_order_confidence is not None:
        _unit_float("reading_order_confidence", reading_order_confidence)
    if not isinstance(evidence_status, StructureEvidenceStatus):
        raise TypeError("evidence_status must be StructureEvidenceStatus")
    if kind is StructureKind.BIBLIOGRAPHY_ENTRY and (
        evidence_status is not StructureEvidenceStatus.OBSERVED
    ):
        raise ValueError("bibliography entries must remain observations")


def _validate_analysis_parts(
    *,
    nodes: tuple[StructureNode, ...],
    warnings: tuple[IngestionWarning, ...],
    source_id: str | None,
    source_blob_id: str | None,
    layout_result_ids: tuple[str, ...],
    input_block_ids: tuple[str, ...],
    processor_name: str | None,
    processor_version: str | None,
    configuration_digest: str | None,
) -> None:
    _require_tuple("nodes", nodes)
    _require_tuple("warnings", warnings)
    _require_tuple("layout_result_ids", layout_result_ids)
    _require_tuple("input_block_ids", input_block_ids)
    if len(nodes) > _MAX_NODES:
        raise ValueError("structure analysis has too many nodes")
    if len(warnings) > _MAX_WARNINGS:
        raise ValueError("structure analysis has too many warnings")
    if any(not isinstance(node, StructureNode) for node in nodes):
        raise TypeError("nodes must contain StructureNode values")
    if any(not isinstance(warning, IngestionWarning) for warning in warnings):
        raise TypeError("warnings must contain IngestionWarning values")
    total_source_spans = sum(len(node.source_spans) for node in nodes) + sum(
        len(warning.source_spans) for warning in warnings
    )
    if total_source_spans > _MAX_SOURCE_SPANS_PER_ANALYSIS:
        raise ValueError("structure analysis has too many source spans")
    total_text_characters = sum(
        len(node.evidence_type)
        + len(node.label or "")
        + len(node.title or "")
        + sum(len(key) + len(value) for key, value in node.evidence)
        for node in nodes
    )
    for warning in warnings:
        _validate_warning(warning)
        total_text_characters += (
            len(warning.code)
            + len(warning.message)
            + len(warning.suggested_recovery or "")
            + sum(len(key) + len(value) for key, value in warning.evidence)
        )
    if total_text_characters > _MAX_ANALYSIS_TEXT_CHARACTERS:
        raise ValueError("structure analysis text exceeds its aggregate limit")
    _unique_strings(
        "layout_result_ids", layout_result_ids, limit=_MAX_LINKS_PER_NODE
    )
    _unique_strings(
        "input_block_ids", input_block_ids, limit=_MAX_INPUT_BLOCK_IDS
    )
    input_block_id_set = set(input_block_ids)
    for node in nodes:
        if not set(node.source_block_ids).issubset(input_block_id_set):
            raise ValueError(
                "structure node source block IDs are not input evidence"
            )
    nodes_by_id = {node.node_id: node for node in nodes}
    if len(nodes_by_id) != len(nodes):
        raise ValueError("structure node IDs must be unique")
    for node in nodes:
        if node.parent_id is not None:
            if node.parent_id not in nodes_by_id:
                raise ValueError("structure parent must exist in the analysis")
            parent = nodes_by_id[node.parent_id]
            if node.node_id not in parent.child_ids:
                raise ValueError(
                    "parent and child relationships must be reciprocal"
                )
        for child_id in node.child_ids:
            if child_id not in nodes_by_id:
                raise ValueError("structure child must exist in the analysis")
            if nodes_by_id[child_id].parent_id != node.node_id:
                raise ValueError(
                    "parent and child relationships must be reciprocal"
                )
        seen: set[str] = set()
        current = node
        while current.parent_id is not None:
            if current.node_id in seen:
                raise ValueError("structure hierarchy cannot contain cycles")
            seen.add(current.node_id)
            current = nodes_by_id[current.parent_id]
    warning_ids = {warning.warning_id for warning in warnings}
    if len(warning_ids) != len(warnings):
        raise ValueError("structure warning IDs must be unique")
    allowed_warning_object_ids = (
        set(nodes_by_id) | set(layout_result_ids) | input_block_id_set
    )
    for warning in warnings:
        if not set(warning.object_ids).issubset(allowed_warning_object_ids):
            raise ValueError("structure warning has unresolved object IDs")
    for node in nodes:
        if not set(node.warning_ids).issubset(warning_ids):
            raise ValueError(
                "structure warning IDs must refer to analysis warnings"
            )
    reading_orders = tuple(
        node.reading_order for node in nodes if node.reading_order is not None
    )
    if len(set(reading_orders)) != len(reading_orders):
        raise ValueError("structure reading orders must be unique")
    if reading_orders and set(reading_orders) != set(
        range(len(reading_orders))
    ):
        raise ValueError("structure reading orders must be contiguous")
    if source_id is not None and source_blob_id is not None:
        _bounded_string("source_id", source_id)
        _bounded_string("source_blob_id", source_blob_id)
        for node in nodes:
            if any(
                span.source_id != source_id
                or span.source_blob_id != source_blob_id
                for span in node.source_spans
            ):
                raise ValueError(
                    "structure spans must refer to the exact analysis source"
                )
        for warning in warnings:
            if any(
                span.source_id != source_id
                or span.source_blob_id != source_blob_id
                for span in warning.source_spans
            ):
                raise ValueError(
                    "structure warning spans must refer to the exact source"
                )
    for name, value in (
        ("processor_name", processor_name),
        ("processor_version", processor_version),
        ("configuration_digest", configuration_digest),
    ):
        if value is not None:
            _bounded_string(name, value)


def _structure_node_id(
    *,
    kind: StructureKind,
    source_spans: tuple[SourceSpan, ...],
    evidence_type: str,
    confidence: float,
    label: str | None,
    title: str | None,
    evidence: Metadata,
    source_block_ids: tuple[str, ...],
    heading_level: int | None,
    heading_confidence: float | None,
    evidence_status: StructureEvidenceStatus,
) -> str:
    return stable_id(
        "structure-node",
        STRUCTURE_CONTRACT_VERSION,
        kind.value,
        tuple(span.identity_parts() for span in source_spans),
        evidence_type,
        float(confidence),
        label,
        title,
        evidence,
        source_block_ids,
        heading_level,
        (float(heading_confidence) if heading_confidence is not None else None),
        evidence_status.value,
    )


def _structure_analysis_id(
    *,
    source_id: str,
    source_blob_id: str,
    nodes: tuple[StructureNode, ...],
    warnings: tuple[IngestionWarning, ...],
    layout_result_ids: tuple[str, ...],
    input_block_ids: tuple[str, ...],
    processor_name: str,
    processor_version: str,
    configuration_digest: str,
) -> str:
    return stable_id(
        "structure-analysis",
        STRUCTURE_CONTRACT_VERSION,
        source_id,
        source_blob_id,
        tuple(
            (
                node.node_id,
                node.parent_id,
                node.child_ids,
                node.warning_ids,
                node.reading_order,
                node.reading_order_confidence,
            )
            for node in nodes
        ),
        tuple(
            (
                warning.warning_id,
                warning.code,
                warning.severity.value,
                warning.message,
                warning.object_ids,
                tuple(
                    span.identity_parts() for span in warning.source_spans
                ),
                warning.evidence,
                warning.suggested_recovery,
            )
            for warning in warnings
        ),
        layout_result_ids,
        input_block_ids,
        processor_name,
        processor_version,
        configuration_digest,
    )


def _validate_warning(warning: IngestionWarning) -> None:
    _bounded_string("warning_id", warning.warning_id)
    _bounded_string("warning code", warning.code)
    if not isinstance(warning.severity, WarningSeverity):
        raise TypeError("warning severity must be WarningSeverity")
    _bounded_text("warning message", warning.message, nonempty=True)
    _unique_strings("warning object_ids", warning.object_ids)
    _require_tuple("warning source_spans", warning.source_spans)
    if len(warning.source_spans) > _MAX_SOURCE_SPANS_PER_NODE:
        raise ValueError("structure warning has too many source spans")
    if any(not isinstance(span, SourceSpan) for span in warning.source_spans):
        raise TypeError("warning source_spans must contain SourceSpan values")
    _validate_metadata(warning.evidence)
    if warning.suggested_recovery is not None:
        _bounded_text("warning suggested recovery", warning.suggested_recovery)
    expected = stable_id(
        "warning",
        warning.code,
        warning.object_ids,
        tuple(span.identity_parts() for span in warning.source_spans),
        warning.evidence,
    )
    if warning.warning_id != expected:
        raise ValueError("structure warning ID is inconsistent")


def _validate_metadata(value: Metadata) -> None:
    _require_tuple("evidence", value)
    if len(value) > 256:
        raise ValueError("structure evidence has too many entries")
    for entry in value:
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise TypeError("structure evidence must contain immutable pairs")
        _bounded_string("evidence key", entry[0])
        _bounded_text("evidence value", entry[1])


def _unique_strings(
    name: str,
    values: tuple[str, ...],
    *,
    limit: int = _MAX_LINKS_PER_NODE,
) -> None:
    _require_tuple(name, values)
    if len(values) > limit:
        raise ValueError(f"{name} has too many values")
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must be unique")
    for value in values:
        _bounded_string(name, value)


def _require_tuple(name: str, value: object) -> None:
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be an immutable tuple")


def _bounded_string(name: str, value: object) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value or len(value) > _MAX_IDENTITY_CHARACTERS:
        raise ValueError(
            f"{name} must contain 1 to {_MAX_IDENTITY_CHARACTERS} characters"
        )
    _valid_unicode(name, value)


def _bounded_text(
    name: str,
    value: object,
    *,
    nonempty: bool = False,
) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if nonempty and not value:
        raise ValueError(f"{name} must be non-empty")
    if len(value) > _MAX_TEXT_CHARACTERS:
        raise ValueError(f"{name} exceeds its character limit")
    _valid_unicode(name, value)


def _valid_unicode(name: str, value: str) -> None:
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise ValueError(f"{name} must be valid UTF-8") from error


def _unit_float(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{name} must be a finite number")
    normalized = float(value)
    if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{name} must be between zero and one")
    return normalized


def _optional_nonnegative_integer(name: str, value: object) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
