from __future__ import annotations

import math
import re
from dataclasses import dataclass, fields, is_dataclass, replace
from enum import Enum, StrEnum

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import (
    BoundingBox,
    ExtractedBlock,
    IngestionWarning,
    Metadata,
    SourceSpan,
    WarningSeverity,
)
from projectkoios.ingestion.tables import (
    TABLE_CONTRACT_VERSION,
    TableAssociationRole,
    TableBoundaryKind,
    TableCandidate,
    TableDetectionResult,
    TableEvidenceStatus,
    TableRegionEvidence,
    TableRuleOrientation,
    TableRuleSegment,
)

TABLE_STRUCTURE_CONTRACT_VERSION = "1.0"
TABLE_STRUCTURE_RECONSTRUCTOR_VERSION = "1"
_MAX_CANDIDATES = 256
_MAX_REGIONS = 16_384
_MAX_COLUMNS = 128
_MAX_ROWS = 100_000
_MAX_CELLS = 1_000_000
_MAX_BLOCKS_PER_CELL = 2_048
_MAX_SOURCE_SPANS = 131_072
_MAX_ASSOCIATIONS = 16_384
_MAX_CONTINUATIONS = 16_384
_MAX_WARNINGS = 16_384
_MAX_TEXT_CHARACTERS = 5_000_000
_MAX_RESULT_BYTES = 128_000_000
_MAX_IDENTITY_CHARACTERS = 4_096
_MAX_METADATA_CHARACTERS = 100_000
_HEADER = re.compile(r"\bheader\b", re.IGNORECASE)


class TableStructureLimitError(ValueError):
    """Raised before reconstruction exceeds a configured hard bound."""


class TableStructureEvidenceStatus(StrEnum):
    """Proposal status with no accepted or validated state."""

    PROPOSED = "proposed"
    AMBIGUOUS = "ambiguous"


class TableCellRole(StrEnum):
    HEADER = "header"
    BODY = "body"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TableStructureConfiguration:
    max_candidates: int = _MAX_CANDIDATES
    max_regions: int = _MAX_REGIONS
    max_columns: int = _MAX_COLUMNS
    max_rows: int = _MAX_ROWS
    max_cells: int = _MAX_CELLS
    max_blocks_per_cell: int = _MAX_BLOCKS_PER_CELL
    max_source_spans: int = _MAX_SOURCE_SPANS
    max_associations: int = _MAX_ASSOCIATIONS
    max_continuations: int = _MAX_CONTINUATIONS
    max_warnings: int = _MAX_WARNINGS
    max_text_characters: int = _MAX_TEXT_CHARACTERS
    max_result_bytes: int = _MAX_RESULT_BYTES
    proposed_confidence_threshold: float = 0.75

    def __post_init__(self) -> None:
        for name, hard_maximum in (
            ("max_candidates", _MAX_CANDIDATES),
            ("max_regions", _MAX_REGIONS),
            ("max_columns", _MAX_COLUMNS),
            ("max_rows", _MAX_ROWS),
            ("max_cells", _MAX_CELLS),
            ("max_blocks_per_cell", _MAX_BLOCKS_PER_CELL),
            ("max_source_spans", _MAX_SOURCE_SPANS),
            ("max_associations", _MAX_ASSOCIATIONS),
            ("max_continuations", _MAX_CONTINUATIONS),
            ("max_warnings", _MAX_WARNINGS),
            ("max_text_characters", _MAX_TEXT_CHARACTERS),
            ("max_result_bytes", _MAX_RESULT_BYTES),
        ):
            value = getattr(self, name)
            _positive_integer(name, value)
            if value > hard_maximum:
                raise TableStructureLimitError(
                    f"{name} exceeds its implementation maximum "
                    f"({hard_maximum})"
                )
        object.__setattr__(
            self,
            "proposed_confidence_threshold",
            _unit_float(
                "proposed_confidence_threshold",
                self.proposed_confidence_threshold,
            ),
        )

    @property
    def configuration_digest(self) -> str:
        return stable_id("table-structure-configuration", self.identity_parts())

    def identity_parts(self) -> tuple[object, ...]:
        return tuple(
            (name, getattr(self, name)) for name in self.__dataclass_fields__
        )


@dataclass(frozen=True)
class TableStructureInput:
    input_id: str
    detection_result: TableDetectionResult
    configuration: TableStructureConfiguration
    contract_version: str = TABLE_STRUCTURE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        detection_result: TableDetectionResult,
        configuration: TableStructureConfiguration | None = None,
    ) -> TableStructureInput:
        actual = configuration or TableStructureConfiguration()
        _validate_input_parts(detection_result, actual)
        return cls(
            input_id=_input_id(detection_result, actual),
            detection_result=detection_result,
            configuration=actual,
        )

    def __post_init__(self) -> None:
        if self.contract_version != TABLE_STRUCTURE_CONTRACT_VERSION:
            raise ValueError("unsupported table structure-input version")
        _validate_input_parts(self.detection_result, self.configuration)
        if self.input_id != _input_id(
            self.detection_result, self.configuration
        ):
            raise ValueError("table structure-input ID is inconsistent")


@dataclass(frozen=True)
class TableColumn:
    column_id: str
    structure_input_id: str
    candidate_id: str
    column_index: int
    normalized_left: float
    normalized_right: float
    source_region_ids: tuple[str, ...]
    confidence: float
    evidence: Metadata
    processor_name: str
    processor_version: str
    configuration_digest: str
    contract_version: str = TABLE_STRUCTURE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        structure_input_id: str,
        candidate_id: str,
        column_index: int,
        normalized_left: float,
        normalized_right: float,
        source_region_ids: tuple[str, ...],
        confidence: float,
        evidence: Metadata,
        processor_name: str,
        processor_version: str,
        configuration_digest: str,
    ) -> TableColumn:
        left, right, normalized_confidence = _validate_column_parts(
            structure_input_id,
            candidate_id,
            column_index,
            normalized_left,
            normalized_right,
            source_region_ids,
            confidence,
            evidence,
            processor_name,
            processor_version,
            configuration_digest,
        )
        column_id = _column_id(
            structure_input_id,
            candidate_id,
            column_index,
            left,
            right,
            source_region_ids,
            normalized_confidence,
            evidence,
            processor_name,
            processor_version,
            configuration_digest,
        )
        return cls(
            column_id=column_id,
            structure_input_id=structure_input_id,
            candidate_id=candidate_id,
            column_index=column_index,
            normalized_left=left,
            normalized_right=right,
            source_region_ids=source_region_ids,
            confidence=normalized_confidence,
            evidence=evidence,
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=configuration_digest,
        )

    def __post_init__(self) -> None:
        if self.contract_version != TABLE_STRUCTURE_CONTRACT_VERSION:
            raise ValueError("unsupported table column version")
        left, right, confidence = _validate_column_parts(
            self.structure_input_id,
            self.candidate_id,
            self.column_index,
            self.normalized_left,
            self.normalized_right,
            self.source_region_ids,
            self.confidence,
            self.evidence,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        )
        object.__setattr__(self, "normalized_left", left)
        object.__setattr__(self, "normalized_right", right)
        object.__setattr__(self, "confidence", confidence)
        if self.column_id != _column_id(
            self.structure_input_id,
            self.candidate_id,
            self.column_index,
            left,
            right,
            self.source_region_ids,
            confidence,
            self.evidence,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        ):
            raise ValueError("table column ID is inconsistent")


@dataclass(frozen=True)
class TableRow:
    row_id: str
    structure_input_id: str
    candidate_id: str
    region_id: str
    page_index: int
    page_row_index: int
    reading_order: int
    source_bounding_box: BoundingBox
    source_block_ids: tuple[str, ...]
    source_spans: tuple[SourceSpan, ...]
    repeated_header: bool
    confidence: float
    evidence: Metadata
    processor_name: str
    processor_version: str
    configuration_digest: str
    contract_version: str = TABLE_STRUCTURE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        structure_input_id: str,
        candidate_id: str,
        region_id: str,
        page_index: int,
        page_row_index: int,
        reading_order: int,
        source_bounding_box: BoundingBox,
        source_block_ids: tuple[str, ...],
        source_spans: tuple[SourceSpan, ...],
        repeated_header: bool,
        confidence: float,
        evidence: Metadata,
        processor_name: str,
        processor_version: str,
        configuration_digest: str,
    ) -> TableRow:
        box, normalized_confidence = _validate_row_parts(
            structure_input_id,
            candidate_id,
            region_id,
            page_index,
            page_row_index,
            reading_order,
            source_bounding_box,
            source_block_ids,
            source_spans,
            repeated_header,
            confidence,
            evidence,
            processor_name,
            processor_version,
            configuration_digest,
        )
        row_id = _row_id(
            structure_input_id,
            candidate_id,
            region_id,
            page_index,
            page_row_index,
            reading_order,
            box,
            source_block_ids,
            source_spans,
            repeated_header,
            normalized_confidence,
            evidence,
            processor_name,
            processor_version,
            configuration_digest,
        )
        return cls(
            row_id=row_id,
            structure_input_id=structure_input_id,
            candidate_id=candidate_id,
            region_id=region_id,
            page_index=page_index,
            page_row_index=page_row_index,
            reading_order=reading_order,
            source_bounding_box=box,
            source_block_ids=source_block_ids,
            source_spans=source_spans,
            repeated_header=repeated_header,
            confidence=normalized_confidence,
            evidence=evidence,
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=configuration_digest,
        )

    def __post_init__(self) -> None:
        if self.contract_version != TABLE_STRUCTURE_CONTRACT_VERSION:
            raise ValueError("unsupported table row version")
        box, confidence = _validate_row_parts(
            self.structure_input_id,
            self.candidate_id,
            self.region_id,
            self.page_index,
            self.page_row_index,
            self.reading_order,
            self.source_bounding_box,
            self.source_block_ids,
            self.source_spans,
            self.repeated_header,
            self.confidence,
            self.evidence,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        )
        object.__setattr__(self, "source_bounding_box", box)
        object.__setattr__(self, "confidence", confidence)
        if self.row_id != _row_id(
            self.structure_input_id,
            self.candidate_id,
            self.region_id,
            self.page_index,
            self.page_row_index,
            self.reading_order,
            box,
            self.source_block_ids,
            self.source_spans,
            self.repeated_header,
            confidence,
            self.evidence,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        ):
            raise ValueError("table row ID is inconsistent")


@dataclass(frozen=True)
class TableCell:
    cell_id: str
    structure_input_id: str
    candidate_id: str
    row_id: str
    page_index: int
    row_index: int
    column_index: int
    row_span: int
    column_span: int
    role: TableCellRole
    evidence_status: TableStructureEvidenceStatus
    proposed_text: str | None
    text_join_method: str | None
    source_texts: tuple[str, ...]
    source_block_ids: tuple[str, ...]
    source_spans: tuple[SourceSpan, ...]
    rendered_region_ids: tuple[str, ...]
    confidence: float
    evidence: Metadata
    warning_ids: tuple[str, ...]
    processor_name: str
    processor_version: str
    configuration_digest: str
    contract_version: str = TABLE_STRUCTURE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        structure_input_id: str,
        candidate_id: str,
        row_id: str,
        page_index: int,
        row_index: int,
        column_index: int,
        row_span: int,
        column_span: int,
        role: TableCellRole,
        evidence_status: TableStructureEvidenceStatus,
        proposed_text: str | None,
        text_join_method: str | None,
        source_texts: tuple[str, ...],
        source_block_ids: tuple[str, ...],
        source_spans: tuple[SourceSpan, ...],
        rendered_region_ids: tuple[str, ...],
        confidence: float,
        evidence: Metadata,
        warning_ids: tuple[str, ...],
        processor_name: str,
        processor_version: str,
        configuration_digest: str,
    ) -> TableCell:
        normalized_confidence = _validate_cell_parts(
            structure_input_id,
            candidate_id,
            row_id,
            page_index,
            row_index,
            column_index,
            row_span,
            column_span,
            role,
            evidence_status,
            proposed_text,
            text_join_method,
            source_texts,
            source_block_ids,
            source_spans,
            rendered_region_ids,
            confidence,
            evidence,
            warning_ids,
            processor_name,
            processor_version,
            configuration_digest,
        )
        cell_id = _cell_id(
            structure_input_id,
            candidate_id,
            row_id,
            page_index,
            row_index,
            column_index,
            row_span,
            column_span,
            role,
            evidence_status,
            proposed_text,
            text_join_method,
            source_texts,
            source_block_ids,
            source_spans,
            rendered_region_ids,
            normalized_confidence,
            evidence,
            processor_name,
            processor_version,
            configuration_digest,
        )
        return cls(
            cell_id=cell_id,
            structure_input_id=structure_input_id,
            candidate_id=candidate_id,
            row_id=row_id,
            page_index=page_index,
            row_index=row_index,
            column_index=column_index,
            row_span=row_span,
            column_span=column_span,
            role=role,
            evidence_status=evidence_status,
            proposed_text=proposed_text,
            text_join_method=text_join_method,
            source_texts=source_texts,
            source_block_ids=source_block_ids,
            source_spans=source_spans,
            rendered_region_ids=rendered_region_ids,
            confidence=normalized_confidence,
            evidence=evidence,
            warning_ids=warning_ids,
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=configuration_digest,
        )

    def __post_init__(self) -> None:
        if self.contract_version != TABLE_STRUCTURE_CONTRACT_VERSION:
            raise ValueError("unsupported table cell version")
        confidence = _validate_cell_parts(
            self.structure_input_id,
            self.candidate_id,
            self.row_id,
            self.page_index,
            self.row_index,
            self.column_index,
            self.row_span,
            self.column_span,
            self.role,
            self.evidence_status,
            self.proposed_text,
            self.text_join_method,
            self.source_texts,
            self.source_block_ids,
            self.source_spans,
            self.rendered_region_ids,
            self.confidence,
            self.evidence,
            self.warning_ids,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        )
        object.__setattr__(self, "confidence", confidence)
        if self.cell_id != _cell_id(
            self.structure_input_id,
            self.candidate_id,
            self.row_id,
            self.page_index,
            self.row_index,
            self.column_index,
            self.row_span,
            self.column_span,
            self.role,
            self.evidence_status,
            self.proposed_text,
            self.text_join_method,
            self.source_texts,
            self.source_block_ids,
            self.source_spans,
            self.rendered_region_ids,
            confidence,
            self.evidence,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        ):
            raise ValueError("table cell ID is inconsistent")


@dataclass(frozen=True)
class TableContinuation:
    continuation_id: str
    structure_input_id: str
    candidate_id: str
    previous_region_id: str
    current_region_id: str
    previous_page_index: int
    current_page_index: int
    association_id: str
    confidence: float
    evidence_status: TableStructureEvidenceStatus
    evidence: Metadata
    processor_name: str
    processor_version: str
    configuration_digest: str
    contract_version: str = TABLE_STRUCTURE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        structure_input_id: str,
        candidate_id: str,
        previous_region_id: str,
        current_region_id: str,
        previous_page_index: int,
        current_page_index: int,
        association_id: str,
        confidence: float,
        evidence_status: TableStructureEvidenceStatus,
        evidence: Metadata,
        processor_name: str,
        processor_version: str,
        configuration_digest: str,
    ) -> TableContinuation:
        normalized = _validate_continuation_parts(
            structure_input_id,
            candidate_id,
            previous_region_id,
            current_region_id,
            previous_page_index,
            current_page_index,
            association_id,
            confidence,
            evidence_status,
            evidence,
            processor_name,
            processor_version,
            configuration_digest,
        )
        continuation_id = _continuation_id(
            structure_input_id,
            candidate_id,
            previous_region_id,
            current_region_id,
            previous_page_index,
            current_page_index,
            association_id,
            normalized,
            evidence_status,
            evidence,
            processor_name,
            processor_version,
            configuration_digest,
        )
        return cls(
            continuation_id=continuation_id,
            structure_input_id=structure_input_id,
            candidate_id=candidate_id,
            previous_region_id=previous_region_id,
            current_region_id=current_region_id,
            previous_page_index=previous_page_index,
            current_page_index=current_page_index,
            association_id=association_id,
            confidence=normalized,
            evidence_status=evidence_status,
            evidence=evidence,
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=configuration_digest,
        )

    def __post_init__(self) -> None:
        if self.contract_version != TABLE_STRUCTURE_CONTRACT_VERSION:
            raise ValueError("unsupported table continuation version")
        confidence = _validate_continuation_parts(
            self.structure_input_id,
            self.candidate_id,
            self.previous_region_id,
            self.current_region_id,
            self.previous_page_index,
            self.current_page_index,
            self.association_id,
            self.confidence,
            self.evidence_status,
            self.evidence,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        )
        object.__setattr__(self, "confidence", confidence)
        if self.continuation_id != _continuation_id(
            self.structure_input_id,
            self.candidate_id,
            self.previous_region_id,
            self.current_region_id,
            self.previous_page_index,
            self.current_page_index,
            self.association_id,
            confidence,
            self.evidence_status,
            self.evidence,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        ):
            raise ValueError("table continuation ID is inconsistent")


@dataclass(frozen=True)
class TableStructure:
    structure_id: str
    structure_input_id: str
    candidate_id: str
    source_label: str | None
    boundary_kind: TableBoundaryKind
    evidence_status: TableStructureEvidenceStatus
    columns: tuple[TableColumn, ...]
    rows: tuple[TableRow, ...]
    cells: tuple[TableCell, ...]
    continuations: tuple[TableContinuation, ...]
    association_ids: tuple[str, ...]
    confidence: float
    evidence: Metadata
    warning_ids: tuple[str, ...]
    processor_name: str
    processor_version: str
    configuration_digest: str
    contract_version: str = TABLE_STRUCTURE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        structure_input_id: str,
        candidate_id: str,
        source_label: str | None,
        boundary_kind: TableBoundaryKind,
        evidence_status: TableStructureEvidenceStatus,
        columns: tuple[TableColumn, ...],
        rows: tuple[TableRow, ...],
        cells: tuple[TableCell, ...],
        continuations: tuple[TableContinuation, ...],
        association_ids: tuple[str, ...],
        confidence: float,
        evidence: Metadata,
        warning_ids: tuple[str, ...],
        processor_name: str,
        processor_version: str,
        configuration_digest: str,
    ) -> TableStructure:
        normalized = _validate_structure_parts(
            structure_input_id,
            candidate_id,
            source_label,
            boundary_kind,
            evidence_status,
            columns,
            rows,
            cells,
            continuations,
            association_ids,
            confidence,
            evidence,
            warning_ids,
            processor_name,
            processor_version,
            configuration_digest,
        )
        structure_id = _structure_id(
            structure_input_id,
            candidate_id,
            source_label,
            boundary_kind,
            evidence_status,
            columns,
            rows,
            cells,
            continuations,
            association_ids,
            normalized,
            evidence,
            processor_name,
            processor_version,
            configuration_digest,
        )
        return cls(
            structure_id=structure_id,
            structure_input_id=structure_input_id,
            candidate_id=candidate_id,
            source_label=source_label,
            boundary_kind=boundary_kind,
            evidence_status=evidence_status,
            columns=columns,
            rows=rows,
            cells=cells,
            continuations=continuations,
            association_ids=association_ids,
            confidence=normalized,
            evidence=evidence,
            warning_ids=warning_ids,
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=configuration_digest,
        )

    def __post_init__(self) -> None:
        if self.contract_version != TABLE_STRUCTURE_CONTRACT_VERSION:
            raise ValueError("unsupported table structure version")
        confidence = _validate_structure_parts(
            self.structure_input_id,
            self.candidate_id,
            self.source_label,
            self.boundary_kind,
            self.evidence_status,
            self.columns,
            self.rows,
            self.cells,
            self.continuations,
            self.association_ids,
            self.confidence,
            self.evidence,
            self.warning_ids,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        )
        object.__setattr__(self, "confidence", confidence)
        if self.structure_id != _structure_id(
            self.structure_input_id,
            self.candidate_id,
            self.source_label,
            self.boundary_kind,
            self.evidence_status,
            self.columns,
            self.rows,
            self.cells,
            self.continuations,
            self.association_ids,
            confidence,
            self.evidence,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        ):
            raise ValueError("table structure ID is inconsistent")


@dataclass(frozen=True)
class TableStructureResult:
    result_id: str
    structure_input: TableStructureInput
    structures: tuple[TableStructure, ...]
    warnings: tuple[IngestionWarning, ...]
    processor_name: str
    processor_version: str
    configuration_digest: str
    contract_version: str = TABLE_STRUCTURE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        structure_input: TableStructureInput,
        structures: tuple[TableStructure, ...],
        warnings: tuple[IngestionWarning, ...],
        processor_name: str,
        processor_version: str,
    ) -> TableStructureResult:
        _preflight_result(
            structure_input,
            structures,
            warnings,
            processor_name,
            processor_version,
        )
        digest = structure_input.configuration.configuration_digest
        _validate_retained_size(
            (
                structure_input,
                structures,
                warnings,
                processor_name,
                processor_version,
            ),
            structure_input.configuration.max_result_bytes,
        )
        return cls(
            result_id=_result_id(
                structure_input.input_id,
                structures,
                warnings,
                processor_name,
                processor_version,
                digest,
            ),
            structure_input=structure_input,
            structures=structures,
            warnings=warnings,
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=digest,
        )

    def __post_init__(self) -> None:
        if self.contract_version != TABLE_STRUCTURE_CONTRACT_VERSION:
            raise ValueError("unsupported table structure-result version")
        _preflight_result(
            self.structure_input,
            self.structures,
            self.warnings,
            self.processor_name,
            self.processor_version,
        )
        _validate_result(self)
        if self.result_id != _result_id(
            self.structure_input.input_id,
            self.structures,
            self.warnings,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        ):
            raise ValueError("table structure-result ID is inconsistent")


@dataclass(frozen=True)
class _Record:
    block: ExtractedBlock
    box: BoundingBox
    order: int

    @property
    def center_x(self) -> float:
        return (self.box[0] + self.box[2]) / 2.0

    @property
    def center_y(self) -> float:
        return (self.box[1] + self.box[3]) / 2.0


@dataclass(frozen=True)
class _WarningSpec:
    code: str
    message: str
    object_ids: tuple[str, ...]
    source_spans: tuple[SourceSpan, ...]
    evidence: Metadata = ()


class DeterministicTableStructureReconstructor:
    """Propose bounded rows, columns, cells, spans, and continuations."""

    name = "deterministic-table-structure-reconstructor"
    version = TABLE_STRUCTURE_RECONSTRUCTOR_VERSION

    def __init__(
        self, configuration: TableStructureConfiguration | None = None
    ) -> None:
        self.configuration = configuration or TableStructureConfiguration()

    @property
    def configuration_digest(self) -> str:
        return self.configuration.configuration_digest

    def reconstruct(
        self, detection_result: TableDetectionResult
    ) -> TableStructureResult:
        structure_input = TableStructureInput.create(
            detection_result=detection_result,
            configuration=self.configuration,
        )
        base_structures: list[TableStructure] = []
        warning_specs: list[list[_WarningSpec]] = []
        for candidate in detection_result.candidates:
            structure, specs = _reconstruct_candidate(
                structure_input,
                candidate,
                self.name,
                self.version,
            )
            base_structures.append(structure)
            warning_specs.append(specs)
        warnings, structures = _materialize_warnings(
            tuple(base_structures), tuple(warning_specs)
        )
        return TableStructureResult.create(
            structure_input=structure_input,
            structures=structures,
            warnings=warnings,
            processor_name=self.name,
            processor_version=self.version,
        )


def _reconstruct_candidate(
    structure_input: TableStructureInput,
    candidate: TableCandidate,
    processor_name: str,
    processor_version: str,
) -> tuple[TableStructure, list[_WarningSpec]]:
    detection = structure_input.detection_result
    configuration = structure_input.configuration
    blocks = {
        block.block_id: block
        for page in detection.detection_input.document.pages
        for block in page.blocks
    }
    rules = {
        segment.segment_id: segment
        for page in detection.detection_input.page_rule_evidence
        for segment in page.segments
    }
    column_count = max(region.column_band_count for region in candidate.regions)
    if column_count > configuration.max_columns:
        raise TableStructureLimitError("columns exceed max_columns")
    region_column_bounds = tuple(
        _column_boundaries(
            region,
            blocks,
            rules,
            column_count,
            detection.detection_input.configuration.column_alignment_tolerance_points,
        )
        for region in candidate.regions
    )
    normalized_bounds = tuple(
        sum(
            bounds[index] / _page_width(detection, region.page_index)
            for region, bounds in zip(
                candidate.regions, region_column_bounds, strict=True
            )
        )
        / len(candidate.regions)
        for index in range(column_count + 1)
    )
    columns = tuple(
        TableColumn.create(
            structure_input_id=structure_input.input_id,
            candidate_id=candidate.candidate_id,
            column_index=index,
            normalized_left=normalized_bounds[index],
            normalized_right=normalized_bounds[index + 1],
            source_region_ids=tuple(
                region.region_evidence_id for region in candidate.regions
            ),
            confidence=min(region.confidence for region in candidate.regions),
            evidence=(("boundary_method", "rules_or_text_midpoints"),),
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=configuration.configuration_digest,
        )
        for index in range(column_count)
    )
    rows: list[TableRow] = []
    cells: list[TableCell] = []
    specs: list[_WarningSpec] = []
    first_header_texts: tuple[str, ...] | None = None
    reading_order = 0
    for region, column_bounds in zip(
        candidate.regions, region_column_bounds, strict=True
    ):
        records = tuple(
            _Record(blocks[block_id], _block_box(blocks[block_id]), order)
            for order, block_id in enumerate(region.block_ids)
        )
        row_groups = _cluster_rows(
            records,
            detection.detection_input.configuration.row_alignment_tolerance_points,
        )
        if len(row_groups) != region.row_band_count:
            raise ValueError("candidate row evidence cannot be reconstructed")
        header_flags = tuple(
            any(_HEADER.search(record.block.text or "") for record in group)
            for group in row_groups
        )
        header_row_index = next(
            (index for index, value in enumerate(header_flags) if value),
            None,
        )
        header_texts = (
            None
            if header_row_index is None
            else tuple(
                record.block.text or ""
                for record in row_groups[header_row_index]
            )
        )
        region_repeats_header = (
            first_header_texts is not None
            and header_texts is not None
            and tuple(_normalized_text(text) for text in header_texts)
            == tuple(_normalized_text(text) for text in first_header_texts)
        )
        if first_header_texts is None and header_texts is not None:
            first_header_texts = header_texts
        row_bounds = _row_boundaries(region, row_groups, rules)
        for page_row_index, group in enumerate(row_groups):
            row_is_header = header_flags[page_row_index]
            repeated_header = region_repeats_header and row_is_header
            source_block_ids = tuple(record.block.block_id for record in group)
            source_spans = tuple(
                span for record in group for span in record.block.source_spans
            )
            row = TableRow.create(
                structure_input_id=structure_input.input_id,
                candidate_id=candidate.candidate_id,
                region_id=region.region_evidence_id,
                page_index=region.page_index,
                page_row_index=page_row_index,
                reading_order=reading_order,
                source_bounding_box=(
                    region.source_bounding_box[0],
                    row_bounds[page_row_index],
                    region.source_bounding_box[2],
                    row_bounds[page_row_index + 1],
                ),
                source_block_ids=source_block_ids,
                source_spans=source_spans,
                repeated_header=repeated_header,
                confidence=region.confidence,
                evidence=(
                    ("row_method", "rules_or_text_midpoints"),
                    ("explicit_header", str(row_is_header).lower()),
                ),
                processor_name=processor_name,
                processor_version=processor_version,
                configuration_digest=configuration.configuration_digest,
            )
            rows.append(row)
            reading_order += 1
            role = (
                TableCellRole.HEADER
                if row_is_header
                else (
                    TableCellRole.UNKNOWN
                    if header_row_index is None
                    or page_row_index < header_row_index
                    else TableCellRole.BODY
                )
            )
            slots: dict[int, list[_Record]] = {
                index: [] for index in range(column_count)
            }
            merged_records = [
                record
                for record in group
                if record.block.block_id in region.merged_cell_signal_block_ids
            ]
            if merged_records:
                merged = merged_records[0]
                cell = _cell_from_records(
                    structure_input,
                    candidate,
                    region,
                    row,
                    page_row_index,
                    0,
                    1,
                    column_count,
                    role,
                    (merged,),
                    TableStructureEvidenceStatus.AMBIGUOUS,
                    processor_name,
                    processor_version,
                )
                cells.append(cell)
                specs.append(
                    _WarningSpec(
                        code="table_structure.merged_span_ambiguous",
                        message=(
                            "A candidate merged row is represented as a "
                            "full-column span proposal"
                        ),
                        object_ids=(cell.cell_id,),
                        source_spans=cell.source_spans,
                    )
                )
                continue
            for record in group:
                column_index = _column_for(record.center_x, column_bounds)
                slots[column_index].append(record)
            for column_index in range(column_count):
                assigned = tuple(slots[column_index])
                if not assigned:
                    status = TableStructureEvidenceStatus.AMBIGUOUS
                elif len(assigned) > 1:
                    status = TableStructureEvidenceStatus.AMBIGUOUS
                else:
                    status = TableStructureEvidenceStatus.PROPOSED
                cell = _cell_from_records(
                    structure_input,
                    candidate,
                    region,
                    row,
                    page_row_index,
                    column_index,
                    1,
                    1,
                    role,
                    assigned,
                    status,
                    processor_name,
                    processor_version,
                )
                cells.append(cell)
                if not assigned:
                    specs.append(
                        _WarningSpec(
                            code="table_structure.empty_cell",
                            message=(
                                "A proposed grid position has no native text "
                                "block and retains rendered-region evidence"
                            ),
                            object_ids=(cell.cell_id,),
                            source_spans=(),
                        )
                    )
                elif len(assigned) > 1:
                    specs.append(
                        _WarningSpec(
                            code="table_structure.multiple_blocks_in_cell",
                            message=(
                                "Multiple native blocks map to one "
                                "proposed cell"
                            ),
                            object_ids=(cell.cell_id,),
                            source_spans=cell.source_spans,
                        )
                    )
        if header_row_index is None:
            specs.append(
                _WarningSpec(
                    code="table_structure.header_unresolved",
                    message="No explicit header evidence was observed",
                    object_ids=(),
                    source_spans=tuple(
                        span
                        for record in row_groups[0]
                        for span in record.block.source_spans
                    ),
                    evidence=(("page_index", str(region.page_index)),),
                )
            )
        if candidate.boundary_kind is TableBoundaryKind.UNRULED:
            specs.append(
                _WarningSpec(
                    code="table_structure.unruled_geometry",
                    message=(
                        "Column and row boundaries rely on native-text geometry"
                    ),
                    object_ids=(),
                    source_spans=region.source_spans,
                )
            )
        elif candidate.boundary_kind is TableBoundaryKind.MIXED:
            specs.append(
                _WarningSpec(
                    code="table_structure.mixed_boundary_geometry",
                    message=(
                        "Table boundaries combine incomplete rules and "
                        "native-text geometry"
                    ),
                    object_ids=(),
                    source_spans=region.source_spans,
                )
            )
    continuations = _continuations(
        structure_input,
        candidate,
        processor_name,
        processor_version,
    )
    if len(rows) > configuration.max_rows:
        raise TableStructureLimitError("rows exceed max_rows")
    if len(cells) > configuration.max_cells:
        raise TableStructureLimitError("cells exceed max_cells")
    if candidate.confidence < configuration.proposed_confidence_threshold:
        specs.append(
            _WarningSpec(
                code="table_structure.low_confidence",
                message=(
                    "Source candidate confidence is below the configured "
                    "structure-proposal threshold"
                ),
                object_ids=(),
                source_spans=candidate.source_spans,
            )
        )
    ambiguous = (
        bool(specs)
        or candidate.evidence_status is TableEvidenceStatus.AMBIGUOUS
    )
    status = (
        TableStructureEvidenceStatus.AMBIGUOUS
        if ambiguous
        else TableStructureEvidenceStatus.PROPOSED
    )
    confidence = max(
        0.0,
        candidate.confidence
        - (0.15 if ambiguous else 0.0)
        - (
            0.05
            if candidate.boundary_kind is TableBoundaryKind.UNRULED
            else 0.0
        ),
    )
    evidence: Metadata = (
        ("column_count", str(len(columns))),
        ("row_count", str(len(rows))),
        ("cell_count", str(len(cells))),
        ("continuation_count", str(len(continuations))),
    )
    structure = TableStructure.create(
        structure_input_id=structure_input.input_id,
        candidate_id=candidate.candidate_id,
        source_label=candidate.source_label,
        boundary_kind=candidate.boundary_kind,
        evidence_status=status,
        columns=columns,
        rows=tuple(rows),
        cells=tuple(cells),
        continuations=continuations,
        association_ids=tuple(
            association.association_id for association in candidate.associations
        ),
        confidence=confidence,
        evidence=evidence,
        warning_ids=(),
        processor_name=processor_name,
        processor_version=processor_version,
        configuration_digest=configuration.configuration_digest,
    )
    specs = [
        replace(spec, object_ids=(structure.structure_id, *spec.object_ids))
        for spec in specs
    ]
    if candidate.evidence_status is TableEvidenceStatus.AMBIGUOUS:
        specs.append(
            _WarningSpec(
                code="table_structure.ambiguous_candidate_inherited",
                message="The source table candidate is ambiguous",
                object_ids=(structure.structure_id,),
                source_spans=candidate.source_spans,
            )
        )
    return structure, specs


def _cell_from_records(
    structure_input: TableStructureInput,
    candidate: TableCandidate,
    region: TableRegionEvidence,
    row: TableRow,
    page_row_index: int,
    column_index: int,
    row_span: int,
    column_span: int,
    role: TableCellRole,
    records: tuple[_Record, ...],
    status: TableStructureEvidenceStatus,
    processor_name: str,
    processor_version: str,
) -> TableCell:
    configuration = structure_input.configuration
    if len(records) > configuration.max_blocks_per_cell:
        raise TableStructureLimitError("cell blocks exceed max_blocks_per_cell")
    texts = tuple(record.block.text or "" for record in records)
    proposed_text = None if not texts else "\n".join(texts)
    join_method = (
        None
        if not texts
        else (
            "single_source_block_exact"
            if len(texts) == 1
            else "source_blocks_newline_in_reading_order"
        )
    )
    source_spans = tuple(
        span for record in records for span in record.block.source_spans
    )
    confidence = (
        0.35
        if not records
        else min(record.block.confidence for record in records)
    )
    evidence: Metadata = (
        ("source_block_count", str(len(records))),
        ("render_scope", "candidate_region"),
    )
    return TableCell.create(
        structure_input_id=structure_input.input_id,
        candidate_id=candidate.candidate_id,
        row_id=row.row_id,
        page_index=region.page_index,
        row_index=row.reading_order,
        column_index=column_index,
        row_span=row_span,
        column_span=column_span,
        role=role,
        evidence_status=status,
        proposed_text=proposed_text,
        text_join_method=join_method,
        source_texts=texts,
        source_block_ids=tuple(record.block.block_id for record in records),
        source_spans=source_spans,
        rendered_region_ids=(region.rendered_region.region_id,),
        confidence=confidence,
        evidence=evidence,
        warning_ids=(),
        processor_name=processor_name,
        processor_version=processor_version,
        configuration_digest=configuration.configuration_digest,
    )


def _continuations(
    structure_input: TableStructureInput,
    candidate: TableCandidate,
    processor_name: str,
    processor_version: str,
) -> tuple[TableContinuation, ...]:
    values: list[TableContinuation] = []
    for previous, current in zip(
        candidate.regions, candidate.regions[1:], strict=False
    ):
        association = next(
            (
                item
                for item in candidate.associations
                if item.page_index == current.page_index
                and item.role is TableAssociationRole.CONTINUATION_LABEL
            ),
            None,
        )
        if association is None:
            raise ValueError("multi-page table lacks continuation association")
        values.append(
            TableContinuation.create(
                structure_input_id=structure_input.input_id,
                candidate_id=candidate.candidate_id,
                previous_region_id=previous.region_evidence_id,
                current_region_id=current.region_evidence_id,
                previous_page_index=previous.page_index,
                current_page_index=current.page_index,
                association_id=association.association_id,
                confidence=min(previous.confidence, current.confidence),
                evidence_status=TableStructureEvidenceStatus.PROPOSED,
                evidence=(("method", "explicit_continuation_label"),),
                processor_name=processor_name,
                processor_version=processor_version,
                configuration_digest=(
                    structure_input.configuration.configuration_digest
                ),
            )
        )
    if len(values) > structure_input.configuration.max_continuations:
        raise TableStructureLimitError("continuations exceed max_continuations")
    return tuple(values)


def _column_boundaries(
    region: TableRegionEvidence,
    blocks: dict[str, ExtractedBlock],
    rules: dict[str, TableRuleSegment],
    column_count: int,
    alignment_tolerance: float,
) -> tuple[float, ...]:
    vertical = sorted(
        {
            segment.start[0]
            for segment_id in region.rule_segment_ids
            if (segment := rules[segment_id]).orientation
            is TableRuleOrientation.VERTICAL
        }
    )
    if len(vertical) == column_count + 1:
        return tuple(vertical)
    records = tuple(
        _Record(blocks[block_id], _block_box(blocks[block_id]), order)
        for order, block_id in enumerate(region.block_ids)
        if block_id not in region.merged_cell_signal_block_ids
    )
    anchors = _cluster_values(
        tuple(record.box[0] for record in records), alignment_tolerance
    )
    if len(anchors) != column_count:
        raise ValueError("candidate columns cannot be reconstructed")
    boundaries = [region.source_bounding_box[0]]
    boundaries.extend(
        (left + right) / 2.0
        for left, right in zip(anchors, anchors[1:], strict=False)
    )
    boundaries.append(region.source_bounding_box[2])
    return tuple(boundaries)


def _row_boundaries(
    region: TableRegionEvidence,
    rows: tuple[tuple[_Record, ...], ...],
    rules: dict[str, TableRuleSegment],
) -> tuple[float, ...]:
    horizontal = sorted(
        {
            segment.start[1]
            for segment_id in region.rule_segment_ids
            if (segment := rules[segment_id]).orientation
            is TableRuleOrientation.HORIZONTAL
        }
    )
    if len(horizontal) == len(rows) + 1:
        return tuple(horizontal)
    centers = tuple(
        sum(record.center_y for record in row) / len(row) for row in rows
    )
    boundaries = [region.source_bounding_box[1]]
    boundaries.extend(
        (top + bottom) / 2.0
        for top, bottom in zip(centers, centers[1:], strict=False)
    )
    boundaries.append(region.source_bounding_box[3])
    return tuple(boundaries)


def _materialize_warnings(
    structures: tuple[TableStructure, ...],
    warning_specs: tuple[list[_WarningSpec], ...],
) -> tuple[tuple[IngestionWarning, ...], tuple[TableStructure, ...]]:
    warnings: list[IngestionWarning] = []
    by_object: dict[str, list[str]] = {}
    for specs in warning_specs:
        for spec in specs:
            warning = IngestionWarning.create(
                code=spec.code,
                severity=WarningSeverity.WARNING,
                message=spec.message,
                object_ids=spec.object_ids,
                source_spans=spec.source_spans,
                evidence=spec.evidence,
            )
            warnings.append(warning)
            for object_id in warning.object_ids:
                by_object.setdefault(object_id, []).append(warning.warning_id)
    final_structures: list[TableStructure] = []
    for structure in structures:
        cells = tuple(
            replace(cell, warning_ids=tuple(by_object.get(cell.cell_id, ())))
            for cell in structure.cells
        )
        final_structures.append(
            replace(
                structure,
                cells=cells,
                warning_ids=tuple(by_object.get(structure.structure_id, ())),
            )
        )
    return tuple(warnings), tuple(final_structures)


def _validate_input_parts(
    detection_result: TableDetectionResult,
    configuration: TableStructureConfiguration,
) -> None:
    if not isinstance(detection_result, TableDetectionResult):
        raise TypeError("detection_result must be TableDetectionResult")
    if not isinstance(configuration, TableStructureConfiguration):
        raise TypeError("configuration must be TableStructureConfiguration")
    if len(detection_result.candidates) > configuration.max_candidates:
        raise TableStructureLimitError("candidates exceed max_candidates")
    region_count = sum(
        len(candidate.regions) for candidate in detection_result.candidates
    )
    if region_count > configuration.max_regions:
        raise TableStructureLimitError("regions exceed max_regions")
    association_count = sum(
        len(candidate.associations) for candidate in detection_result.candidates
    )
    if association_count > configuration.max_associations:
        raise TableStructureLimitError("associations exceed max_associations")
    predicted_rows = sum(
        region.row_band_count
        for candidate in detection_result.candidates
        for region in candidate.regions
    )
    if predicted_rows > configuration.max_rows:
        raise TableStructureLimitError("rows exceed max_rows")
    predicted_cells = sum(
        region.row_band_count
        * max(item.column_band_count for item in candidate.regions)
        for candidate in detection_result.candidates
        for region in candidate.regions
    )
    if predicted_cells > configuration.max_cells:
        raise TableStructureLimitError("cells exceed max_cells")
    if any(
        region.column_band_count > configuration.max_columns
        for candidate in detection_result.candidates
        for region in candidate.regions
    ):
        raise TableStructureLimitError("columns exceed max_columns")
    input_span_count = sum(
        len(region.source_spans)
        for candidate in detection_result.candidates
        for region in candidate.regions
    ) + sum(
        len(association.source_spans)
        for candidate in detection_result.candidates
        for association in candidate.associations
    )
    if input_span_count > configuration.max_source_spans:
        raise TableStructureLimitError("source spans exceed max_source_spans")
    source_blocks = {
        block.block_id: block
        for page in detection_result.detection_input.document.pages
        for block in page.blocks
    }
    input_text_count = sum(
        len(source_blocks[block_id].text or "")
        for candidate in detection_result.candidates
        for region in candidate.regions
        for block_id in region.block_ids
    )
    if input_text_count > configuration.max_text_characters:
        raise TableStructureLimitError("cell text exceeds max_text_characters")


def _input_id(
    detection_result: TableDetectionResult,
    configuration: TableStructureConfiguration,
) -> str:
    return stable_id(
        "table-structure-input",
        TABLE_STRUCTURE_CONTRACT_VERSION,
        TABLE_CONTRACT_VERSION,
        detection_result.result_id,
        tuple(
            (candidate.candidate_id, candidate.warning_ids)
            for candidate in detection_result.candidates
        ),
        configuration.identity_parts(),
    )


def _validate_result(result: TableStructureResult) -> None:
    input_value = result.structure_input
    configuration = input_value.configuration
    if result.configuration_digest != configuration.configuration_digest:
        raise ValueError("structure result configuration is inconsistent")
    candidates = {
        candidate.candidate_id: candidate
        for candidate in input_value.detection_result.candidates
    }
    if len(result.structures) != len(candidates):
        raise ValueError("every table candidate must have one structure")
    warning_by_id = {warning.warning_id: warning for warning in result.warnings}
    if len(warning_by_id) != len(result.warnings):
        raise ValueError("table structure warnings must be unique")
    allowed_warning_object_ids = {
        object_id
        for structure in result.structures
        for object_id in (
            structure.structure_id,
            *(cell.cell_id for cell in structure.cells),
        )
    }
    if any(
        object_id not in allowed_warning_object_ids
        for warning in result.warnings
        for object_id in warning.object_ids
    ):
        raise ValueError("table structure warning references an unknown object")
    seen_candidates: set[str] = set()
    total_rows = 0
    total_cells = 0
    total_text = 0
    for structure in result.structures:
        candidate = candidates.get(structure.candidate_id)
        if candidate is None or structure.candidate_id in seen_candidates:
            raise ValueError("structure candidate mapping is inconsistent")
        seen_candidates.add(structure.candidate_id)
        if structure.structure_input_id != input_value.input_id:
            raise ValueError("structure input identity is inconsistent")
        if (
            structure.processor_name != result.processor_name
            or structure.processor_version != result.processor_version
            or structure.configuration_digest != result.configuration_digest
        ):
            raise ValueError(
                "structure processor/configuration is inconsistent"
            )
        if structure.source_label != candidate.source_label:
            raise ValueError("structure source label is inconsistent")
        if structure.boundary_kind is not candidate.boundary_kind:
            raise ValueError("structure boundary kind is inconsistent")
        if structure.association_ids != tuple(
            association.association_id for association in candidate.associations
        ):
            raise ValueError("structure associations are inconsistent")
        _validate_structure_against_candidate(
            structure, candidate, input_value.detection_result
        )
        expected_warning_ids = tuple(
            warning.warning_id
            for warning in result.warnings
            if structure.structure_id in warning.object_ids
        )
        if structure.warning_ids != expected_warning_ids:
            raise ValueError("structure warning links are incomplete")
        for cell in structure.cells:
            expected_cell_warnings = tuple(
                warning.warning_id
                for warning in result.warnings
                if cell.cell_id in warning.object_ids
            )
            if cell.warning_ids != expected_cell_warnings:
                raise ValueError("cell warning links are incomplete")
            if not set(cell.warning_ids).issubset(warning_by_id):
                raise ValueError("cell references an unknown warning")
            total_text += sum(len(text) for text in cell.source_texts)
        total_rows += len(structure.rows)
        total_cells += len(structure.cells)
    if total_rows > configuration.max_rows:
        raise TableStructureLimitError("rows exceed max_rows")
    if total_cells > configuration.max_cells:
        raise TableStructureLimitError("cells exceed max_cells")
    if total_text > configuration.max_text_characters:
        raise TableStructureLimitError("cell text exceeds max_text_characters")
    if len(result.warnings) > configuration.max_warnings:
        raise TableStructureLimitError("warnings exceed max_warnings")
    _validate_retained_size(result, configuration.max_result_bytes)


def _validate_structure_against_candidate(
    structure: TableStructure,
    candidate: TableCandidate,
    detection_result: TableDetectionResult,
) -> None:
    block_by_id = {
        block.block_id: block
        for page in detection_result.detection_input.document.pages
        for block in page.blocks
    }
    region_by_id = {
        region.region_evidence_id: region for region in candidate.regions
    }
    row_by_id = {row.row_id: row for row in structure.rows}
    if tuple(column.column_index for column in structure.columns) != tuple(
        range(len(structure.columns))
    ):
        raise ValueError("structure columns are not contiguous")
    expected_region_ids = tuple(region_by_id)
    for index, column in enumerate(structure.columns):
        if (
            column.structure_input_id != structure.structure_input_id
            or column.candidate_id != structure.candidate_id
            or column.processor_name != structure.processor_name
            or column.processor_version != structure.processor_version
            or column.configuration_digest != structure.configuration_digest
        ):
            raise ValueError("column derivation evidence is inconsistent")
        if column.source_region_ids != expected_region_ids:
            raise ValueError("column source regions are inconsistent")
        if index and not math.isclose(
            structure.columns[index - 1].normalized_right,
            column.normalized_left,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("normalized column boundaries are not contiguous")
    if tuple(row.reading_order for row in structure.rows) != tuple(
        range(len(structure.rows))
    ):
        raise ValueError("structure row order is not contiguous")
    page_row_indexes: dict[str, list[int]] = {
        region_id: [] for region_id in region_by_id
    }
    for row in structure.rows:
        region = region_by_id.get(row.region_id)
        if region is None or row.page_index != region.page_index:
            raise ValueError("row region evidence is inconsistent")
        if (
            row.structure_input_id != structure.structure_input_id
            or row.candidate_id != structure.candidate_id
            or row.processor_name != structure.processor_name
            or row.processor_version != structure.processor_version
            or row.configuration_digest != structure.configuration_digest
        ):
            raise ValueError("row derivation evidence is inconsistent")
        page_row_indexes[row.region_id].append(row.page_row_index)
        x0, y0, x1, y1 = row.source_bounding_box
        rx0, ry0, rx1, ry1 = region.source_bounding_box
        if x0 < rx0 or y0 < ry0 or x1 > rx1 or y1 > ry1:
            raise ValueError("row bounds exceed the candidate region")
    if any(
        tuple(indexes) != tuple(range(len(indexes)))
        for indexes in page_row_indexes.values()
    ):
        raise ValueError("page-local row indexes are not contiguous")
    occupied: set[tuple[int, int]] = set()
    assigned_by_region: dict[str, list[str]] = {
        region_id: [] for region_id in region_by_id
    }
    for cell in structure.cells:
        cell_row = row_by_id.get(cell.row_id)
        if cell_row is None:
            raise ValueError("cell references an unknown row")
        if (
            cell.row_index != cell_row.reading_order
            or cell.page_index != cell_row.page_index
        ):
            raise ValueError("cell row evidence is inconsistent")
        if (
            cell.structure_input_id != structure.structure_input_id
            or cell.candidate_id != structure.candidate_id
            or cell.processor_name != structure.processor_name
            or cell.processor_version != structure.processor_version
            or cell.configuration_digest != structure.configuration_digest
        ):
            raise ValueError("cell derivation evidence is inconsistent")
        if cell.column_index + cell.column_span > len(structure.columns):
            raise ValueError("cell column span exceeds table columns")
        for row_offset in range(cell.row_span):
            covered_row_index = cell.row_index + row_offset
            if covered_row_index >= len(structure.rows):
                raise ValueError("cell row span exceeds table rows")
            covered_row = structure.rows[covered_row_index]
            if (
                covered_row.page_index != cell_row.page_index
                or covered_row.region_id != cell_row.region_id
            ):
                raise ValueError("cell row span crosses a page region")
            for column_offset in range(cell.column_span):
                position = (
                    covered_row_index,
                    cell.column_index + column_offset,
                )
                if position in occupied:
                    raise ValueError("table cells overlap")
                occupied.add(position)
        region = region_by_id[cell_row.region_id]
        if cell.rendered_region_ids != (region.rendered_region.region_id,):
            raise ValueError("cell rendered evidence is inconsistent")
        source_blocks = tuple(
            block_by_id[item] for item in cell.source_block_ids
        )
        if cell.source_texts != tuple(
            block.text or "" for block in source_blocks
        ):
            raise ValueError("cell source text is inconsistent")
        if cell.source_spans != tuple(
            span for block in source_blocks for span in block.source_spans
        ):
            raise ValueError("cell source spans are inconsistent")
        assigned_by_region[cell_row.region_id].extend(cell.source_block_ids)
        expected_text = (
            None if not cell.source_texts else "\n".join(cell.source_texts)
        )
        if cell.proposed_text != expected_text:
            raise ValueError("cell proposed text is inconsistent")
        if not cell.source_block_ids and not cell.rendered_region_ids:
            raise ValueError("cell lacks source block or rendered evidence")
    expected_positions = {
        (row.reading_order, column.column_index)
        for row in structure.rows
        for column in structure.columns
    }
    if occupied != expected_positions:
        raise ValueError("table cell grid is incomplete")
    for region_id, assigned in assigned_by_region.items():
        if tuple(assigned) != region_by_id[region_id].block_ids:
            raise ValueError(
                "region source blocks are not assigned exactly once"
            )
    cells_by_row: dict[str, list[TableCell]] = {
        row_id: [] for row_id in row_by_id
    }
    for cell in structure.cells:
        cells_by_row[cell.row_id].append(cell)
    for row in structure.rows:
        row_cells = cells_by_row[row.row_id]
        expected_block_ids = tuple(
            block_id for cell in row_cells for block_id in cell.source_block_ids
        )
        expected_spans = tuple(
            span for cell in row_cells for span in cell.source_spans
        )
        if (
            row.source_block_ids != expected_block_ids
            or row.source_spans != expected_spans
        ):
            raise ValueError(
                "row source evidence is inconsistent with its cells"
            )
    association_by_id = {
        association.association_id: association
        for association in candidate.associations
    }
    for continuation in structure.continuations:
        association = association_by_id.get(continuation.association_id)
        if (
            association is None
            or association.role is not TableAssociationRole.CONTINUATION_LABEL
            or association.page_index != continuation.current_page_index
        ):
            raise ValueError("continuation association is inconsistent")
        if (
            continuation.structure_input_id != structure.structure_input_id
            or continuation.candidate_id != structure.candidate_id
            or continuation.processor_name != structure.processor_name
            or continuation.processor_version != structure.processor_version
            or continuation.configuration_digest
            != structure.configuration_digest
        ):
            raise ValueError("continuation derivation evidence is inconsistent")
    continuation_pairs = tuple(
        (item.previous_region_id, item.current_region_id)
        for item in structure.continuations
    )
    expected_pairs = tuple(
        (left.region_evidence_id, right.region_evidence_id)
        for left, right in zip(
            candidate.regions, candidate.regions[1:], strict=False
        )
    )
    if continuation_pairs != expected_pairs:
        raise ValueError("table continuations are inconsistent")


def _validate_column_parts(
    structure_input_id: str,
    candidate_id: str,
    column_index: int,
    normalized_left: float,
    normalized_right: float,
    source_region_ids: tuple[str, ...],
    confidence: float,
    evidence: Metadata,
    processor_name: str,
    processor_version: str,
    configuration_digest: str,
) -> tuple[float, float, float]:
    _identity_fields(
        structure_input_id,
        candidate_id,
        processor_name,
        processor_version,
        configuration_digest,
    )
    _nonnegative_integer("column index", column_index)
    left = _unit_float("normalized column left", normalized_left)
    right = _unit_float("normalized column right", normalized_right)
    if right <= left:
        raise ValueError("normalized column bounds must have positive width")
    _unique_strings(
        "column source region IDs", source_region_ids, required=True
    )
    _validate_metadata(evidence)
    return left, right, _unit_float("column confidence", confidence)


def _validate_row_parts(
    structure_input_id: str,
    candidate_id: str,
    region_id: str,
    page_index: int,
    page_row_index: int,
    reading_order: int,
    source_bounding_box: BoundingBox,
    source_block_ids: tuple[str, ...],
    source_spans: tuple[SourceSpan, ...],
    repeated_header: bool,
    confidence: float,
    evidence: Metadata,
    processor_name: str,
    processor_version: str,
    configuration_digest: str,
) -> tuple[BoundingBox, float]:
    _identity_fields(
        structure_input_id,
        candidate_id,
        region_id,
        processor_name,
        processor_version,
        configuration_digest,
    )
    _nonnegative_integer("row page index", page_index)
    _nonnegative_integer("page row index", page_row_index)
    _nonnegative_integer("row reading order", reading_order)
    box = _validated_box(source_bounding_box)
    _unique_strings("row source block IDs", source_block_ids, required=True)
    _validate_spans(source_spans)
    if not isinstance(repeated_header, bool):
        raise TypeError("repeated_header must be a boolean")
    _validate_metadata(evidence)
    return box, _unit_float("row confidence", confidence)


def _validate_cell_parts(
    structure_input_id: str,
    candidate_id: str,
    row_id: str,
    page_index: int,
    row_index: int,
    column_index: int,
    row_span: int,
    column_span: int,
    role: TableCellRole,
    evidence_status: TableStructureEvidenceStatus,
    proposed_text: str | None,
    text_join_method: str | None,
    source_texts: tuple[str, ...],
    source_block_ids: tuple[str, ...],
    source_spans: tuple[SourceSpan, ...],
    rendered_region_ids: tuple[str, ...],
    confidence: float,
    evidence: Metadata,
    warning_ids: tuple[str, ...],
    processor_name: str,
    processor_version: str,
    configuration_digest: str,
) -> float:
    _identity_fields(
        structure_input_id,
        candidate_id,
        row_id,
        processor_name,
        processor_version,
        configuration_digest,
    )
    _nonnegative_integer("cell page index", page_index)
    _nonnegative_integer("cell row index", row_index)
    _nonnegative_integer("cell column index", column_index)
    _positive_integer("cell row span", row_span)
    _positive_integer("cell column span", column_span)
    if row_span > _MAX_ROWS or column_span > _MAX_COLUMNS:
        raise TableStructureLimitError("cell span exceeds its hard limit")
    if not isinstance(role, TableCellRole):
        raise TypeError("cell role is unsupported")
    if not isinstance(evidence_status, TableStructureEvidenceStatus):
        raise TypeError("cell evidence status is unsupported")
    if proposed_text is not None:
        _bounded_text("cell proposed text", proposed_text)
    if text_join_method is not None:
        _bounded_string(
            "cell text join method", text_join_method, nonempty=True
        )
    if not isinstance(source_texts, tuple):
        raise TypeError("cell source texts must be an immutable tuple")
    for text in source_texts:
        _bounded_text("cell source text", text)
    _unique_strings("cell source block IDs", source_block_ids)
    if len(source_block_ids) > _MAX_BLOCKS_PER_CELL:
        raise TableStructureLimitError(
            "cell source blocks exceed their hard limit"
        )
    if len(source_texts) != len(source_block_ids):
        raise ValueError("cell source texts and blocks must align")
    if source_spans:
        _validate_spans(source_spans)
    elif source_block_ids:
        raise ValueError("source-backed cell requires source spans")
    _unique_strings(
        "cell rendered region IDs", rendered_region_ids, required=True
    )
    _unique_strings("cell warning IDs", warning_ids)
    _validate_metadata(evidence)
    return _unit_float("cell confidence", confidence)


def _validate_continuation_parts(
    structure_input_id: str,
    candidate_id: str,
    previous_region_id: str,
    current_region_id: str,
    previous_page_index: int,
    current_page_index: int,
    association_id: str,
    confidence: float,
    evidence_status: TableStructureEvidenceStatus,
    evidence: Metadata,
    processor_name: str,
    processor_version: str,
    configuration_digest: str,
) -> float:
    _identity_fields(
        structure_input_id,
        candidate_id,
        previous_region_id,
        current_region_id,
        association_id,
        processor_name,
        processor_version,
        configuration_digest,
    )
    _nonnegative_integer("previous page index", previous_page_index)
    _nonnegative_integer("current page index", current_page_index)
    if current_page_index != previous_page_index + 1:
        raise ValueError("table continuation pages must be adjacent")
    if not isinstance(evidence_status, TableStructureEvidenceStatus):
        raise TypeError("continuation evidence status is unsupported")
    _validate_metadata(evidence)
    return _unit_float("continuation confidence", confidence)


def _validate_structure_parts(
    structure_input_id: str,
    candidate_id: str,
    source_label: str | None,
    boundary_kind: TableBoundaryKind,
    evidence_status: TableStructureEvidenceStatus,
    columns: tuple[TableColumn, ...],
    rows: tuple[TableRow, ...],
    cells: tuple[TableCell, ...],
    continuations: tuple[TableContinuation, ...],
    association_ids: tuple[str, ...],
    confidence: float,
    evidence: Metadata,
    warning_ids: tuple[str, ...],
    processor_name: str,
    processor_version: str,
    configuration_digest: str,
) -> float:
    _identity_fields(
        structure_input_id,
        candidate_id,
        processor_name,
        processor_version,
        configuration_digest,
    )
    if source_label is not None:
        _bounded_string("table source label", source_label, nonempty=True)
    if not isinstance(boundary_kind, TableBoundaryKind):
        raise TypeError("table boundary kind is unsupported")
    if not isinstance(evidence_status, TableStructureEvidenceStatus):
        raise TypeError("table structure evidence status is unsupported")
    for name, values, expected_type, hard_limit in (
        ("columns", columns, TableColumn, _MAX_COLUMNS),
        ("rows", rows, TableRow, _MAX_ROWS),
        ("cells", cells, TableCell, _MAX_CELLS),
        ("continuations", continuations, TableContinuation, _MAX_CONTINUATIONS),
    ):
        if not isinstance(values, tuple):
            raise TypeError(f"{name} must be an immutable tuple")
        if not values and name in ("columns", "rows", "cells"):
            raise ValueError(f"table structure requires {name}")
        if len(values) > hard_limit:
            raise TableStructureLimitError(f"{name} exceed their hard limit")
        if any(not isinstance(item, expected_type) for item in values):
            raise TypeError(f"{name} contain an unsupported value")
    _unique_strings("structure association IDs", association_ids)
    _unique_strings("structure warning IDs", warning_ids)
    _validate_metadata(evidence)
    return _unit_float("table structure confidence", confidence)


def _column_id(*values: object) -> str:
    return stable_id("table-column", *values)


def _row_id(
    structure_input_id: str,
    candidate_id: str,
    region_id: str,
    page_index: int,
    page_row_index: int,
    reading_order: int,
    source_bounding_box: BoundingBox,
    source_block_ids: tuple[str, ...],
    source_spans: tuple[SourceSpan, ...],
    repeated_header: bool,
    confidence: float,
    evidence: Metadata,
    processor_name: str,
    processor_version: str,
    configuration_digest: str,
) -> str:
    return stable_id(
        "table-row",
        structure_input_id,
        candidate_id,
        region_id,
        page_index,
        page_row_index,
        reading_order,
        source_bounding_box,
        source_block_ids,
        tuple(span.identity_parts() for span in source_spans),
        repeated_header,
        confidence,
        evidence,
        processor_name,
        processor_version,
        configuration_digest,
    )


def _cell_id(
    structure_input_id: str,
    candidate_id: str,
    row_id: str,
    page_index: int,
    row_index: int,
    column_index: int,
    row_span: int,
    column_span: int,
    role: TableCellRole,
    evidence_status: TableStructureEvidenceStatus,
    proposed_text: str | None,
    text_join_method: str | None,
    source_texts: tuple[str, ...],
    source_block_ids: tuple[str, ...],
    source_spans: tuple[SourceSpan, ...],
    rendered_region_ids: tuple[str, ...],
    confidence: float,
    evidence: Metadata,
    processor_name: str,
    processor_version: str,
    configuration_digest: str,
) -> str:
    return stable_id(
        "table-cell",
        structure_input_id,
        candidate_id,
        row_id,
        page_index,
        row_index,
        column_index,
        row_span,
        column_span,
        role.value,
        evidence_status.value,
        proposed_text,
        text_join_method,
        source_texts,
        source_block_ids,
        tuple(span.identity_parts() for span in source_spans),
        rendered_region_ids,
        confidence,
        evidence,
        processor_name,
        processor_version,
        configuration_digest,
    )


def _continuation_id(*values: object) -> str:
    return stable_id("table-continuation", *values)


def _structure_id(
    structure_input_id: str,
    candidate_id: str,
    source_label: str | None,
    boundary_kind: TableBoundaryKind,
    evidence_status: TableStructureEvidenceStatus,
    columns: tuple[TableColumn, ...],
    rows: tuple[TableRow, ...],
    cells: tuple[TableCell, ...],
    continuations: tuple[TableContinuation, ...],
    association_ids: tuple[str, ...],
    confidence: float,
    evidence: Metadata,
    processor_name: str,
    processor_version: str,
    configuration_digest: str,
) -> str:
    return stable_id(
        "table-structure",
        structure_input_id,
        candidate_id,
        source_label,
        boundary_kind.value,
        evidence_status.value,
        tuple(column.column_id for column in columns),
        tuple(row.row_id for row in rows),
        tuple(cell.cell_id for cell in cells),
        tuple(item.continuation_id for item in continuations),
        association_ids,
        confidence,
        evidence,
        processor_name,
        processor_version,
        configuration_digest,
    )


def _result_id(
    input_id: str,
    structures: tuple[TableStructure, ...],
    warnings: tuple[IngestionWarning, ...],
    processor_name: str,
    processor_version: str,
    configuration_digest: str,
) -> str:
    return stable_id(
        "table-structure-result",
        input_id,
        tuple(
            (
                structure.structure_id,
                structure.warning_ids,
                tuple(
                    (cell.cell_id, cell.warning_ids) for cell in structure.cells
                ),
            )
            for structure in structures
        ),
        tuple(
            (
                warning.warning_id,
                warning.code,
                warning.object_ids,
                tuple(span.identity_parts() for span in warning.source_spans),
                warning.evidence,
            )
            for warning in warnings
        ),
        processor_name,
        processor_version,
        configuration_digest,
    )


def _preflight_result(
    structure_input: TableStructureInput,
    structures: tuple[TableStructure, ...],
    warnings: tuple[IngestionWarning, ...],
    processor_name: str,
    processor_version: str,
) -> None:
    if not isinstance(structure_input, TableStructureInput):
        raise TypeError("structure_input must be TableStructureInput")
    if not isinstance(structures, tuple) or not isinstance(warnings, tuple):
        raise TypeError("result collections must be immutable tuples")
    if len(structures) > structure_input.configuration.max_candidates:
        raise TableStructureLimitError("structures exceed max_candidates")
    if len(warnings) > structure_input.configuration.max_warnings:
        raise TableStructureLimitError("warnings exceed max_warnings")
    if any(not isinstance(item, TableStructure) for item in structures):
        raise TypeError("structures contain an unsupported value")
    if any(not isinstance(item, IngestionWarning) for item in warnings):
        raise TypeError("warnings contain an unsupported value")
    _identity_fields(processor_name, processor_version)


def _cluster_rows(
    records: tuple[_Record, ...], tolerance: float
) -> tuple[tuple[_Record, ...], ...]:
    rows: list[list[_Record]] = []
    centers: list[float] = []
    for record in sorted(
        records, key=lambda item: (item.center_y, item.box[0])
    ):
        if not rows or abs(record.center_y - centers[-1]) > tolerance:
            rows.append([record])
            centers.append(record.center_y)
        else:
            rows[-1].append(record)
            centers[-1] = sum(item.center_y for item in rows[-1]) / len(
                rows[-1]
            )
    return tuple(
        tuple(sorted(row, key=lambda item: item.box[0])) for row in rows
    )


def _cluster_values(
    values: tuple[float, ...], tolerance: float
) -> tuple[float, ...]:
    groups: list[list[float]] = []
    for value in sorted(values):
        if (
            not groups
            or abs(value - sum(groups[-1]) / len(groups[-1])) > tolerance
        ):
            groups.append([value])
        else:
            groups[-1].append(value)
    return tuple(sum(group) / len(group) for group in groups)


def _column_for(center_x: float, boundaries: tuple[float, ...]) -> int:
    for index, (left, right) in enumerate(
        zip(boundaries, boundaries[1:], strict=False)
    ):
        if left <= center_x <= right:
            return index
    return len(boundaries) - 2


def _page_width(result: TableDetectionResult, page_index: int) -> float:
    return next(
        page.width
        for page in result.detection_input.document.pages
        if page.page_index == page_index
    )


def _block_box(block: ExtractedBlock) -> BoundingBox:
    boxes = tuple(
        span.bounding_box
        for span in block.source_spans
        if span.bounding_box is not None
    )
    if not boxes:
        raise ValueError("table source block lacks geometry")
    return _validated_box(
        (
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            max(box[2] for box in boxes),
            max(box[3] for box in boxes),
        )
    )


def _normalized_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _identity_fields(*values: str) -> None:
    for value in values:
        _bounded_string("identity field", value, nonempty=True)


def _unique_strings(
    name: str, values: tuple[str, ...], *, required: bool = False
) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{name} must be an immutable tuple")
    if required and not values:
        raise ValueError(f"{name} must be non-empty")
    for value in values:
        _bounded_string(name, value, nonempty=True)
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must be unique")


def _validate_spans(spans: tuple[SourceSpan, ...]) -> None:
    if not isinstance(spans, tuple) or not spans:
        raise ValueError("source spans must be a non-empty immutable tuple")
    if len(spans) > _MAX_SOURCE_SPANS:
        raise TableStructureLimitError("source spans exceed their hard limit")
    if any(not isinstance(span, SourceSpan) for span in spans):
        raise TypeError("source spans contain an unsupported value")


def _validate_metadata(value: Metadata) -> None:
    if not isinstance(value, tuple):
        raise TypeError("metadata must be an immutable tuple")
    total = 0
    for entry in value:
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise TypeError("metadata must contain immutable pairs")
        key, item = entry
        _bounded_string("metadata key", key, nonempty=True)
        _bounded_string("metadata value", item)
        total += len(key) + len(item)
        if total > _MAX_METADATA_CHARACTERS:
            raise TableStructureLimitError("metadata exceeds its hard limit")


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
        raise TableStructureLimitError(f"{name} exceeds its hard limit")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(f"{name} must be valid UTF-8") from error


def _bounded_text(name: str, value: object) -> None:
    _bounded_string(name, value, limit=_MAX_TEXT_CHARACTERS)


def _positive_integer(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _nonnegative_integer(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _finite_float(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _unit_float(name: str, value: object) -> float:
    result = _finite_float(name, value)
    if not 0.0 <= result <= 1.0:
        raise ValueError(f"{name} must be within [0, 1]")
    return result


def _validated_box(value: object) -> BoundingBox:
    if not isinstance(value, tuple) or len(value) != 4:
        raise TypeError("bounding box must be an immutable four-value tuple")
    x0, y0, x1, y1 = (
        _finite_float("bounding-box coordinate", item) for item in value
    )
    if x1 <= x0 or y1 <= y0:
        raise ValueError("bounding box must have positive area")
    return (x0, y0, x1, y1)


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
                    field.name == "content"
                    and item.__class__.__name__ == "RenderedRegion"
                ):
                    continue
                stack.append(getattr(item, field.name))
        else:
            raise TypeError("table structure contains unsupported evidence")
        if total > limit:
            raise TableStructureLimitError(
                "table structure result exceeds max_result_bytes"
            )
