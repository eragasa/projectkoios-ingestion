"""cross-object table-structure validation."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from typing import TYPE_CHECKING, ClassVar

from projectkoios.ingestion.base import AbstractValidation
from projectkoios.ingestion.models import (
    IngestionWarning,
)
from projectkoios.ingestion.tables.contracts import (
    TableCandidate,
    TableDetectionResult,
)
from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.constants import (
    TABLE_STRUCTURE_CONTRACT_VERSION,
)
from projectkoios.ingestion.tables.structure.limit_error import (
    TableStructureLimitError,
)

if TYPE_CHECKING:
    from projectkoios.ingestion.tables.structure.configuration import (
        TableStructureConfiguration,
    )
    from projectkoios.ingestion.tables.structure.request import (
        TableStructureRequest,
    )
    from projectkoios.ingestion.tables.structure.result import (
        TableStructureResult,
    )
    from projectkoios.ingestion.tables.structure.structure import TableStructure


@dataclass(frozen=True)
class TableStructureValidation(
    AbstractTableStructureDataObject, AbstractValidation
):
    """Record successful validation of one table-structure result."""

    CONTRACT_NAME: ClassVar[str] = "table-structure-validation"
    CONTRACT_VERSION: ClassVar[str] = TABLE_STRUCTURE_CONTRACT_VERSION

    result_id: str

    def __post_init__(self) -> None:
        self._validate_identity_fields(self.result_id)

    @classmethod
    def create(
        cls, *, result: TableStructureResult
    ) -> TableStructureValidation:
        cls._validate_result(result)
        return cls(result_id=result.result_id)

    @staticmethod
    def _validate_input_parts(
        detection_result: TableDetectionResult,
        configuration: TableStructureConfiguration,
    ) -> None:
        from projectkoios.ingestion.tables.structure.configuration import (
            TableStructureConfiguration,
        )

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
            len(candidate.associations)
            for candidate in detection_result.candidates
        )
        if association_count > configuration.max_associations:
            raise TableStructureLimitError(
                "associations exceed max_associations"
            )
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
            raise TableStructureLimitError(
                "source spans exceed max_source_spans"
            )
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
            raise TableStructureLimitError(
                "cell text exceeds max_text_characters"
            )

    @staticmethod
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
        warning_by_id = {
            warning.warning_id: warning for warning in result.warnings
        }
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
            raise ValueError(
                "table structure warning references an unknown object"
            )
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
                association.association_id
                for association in candidate.associations
            ):
                raise ValueError("structure associations are inconsistent")
            TableStructureValidation._validate_structure_against_candidate(
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
            raise TableStructureLimitError(
                "cell text exceeds max_text_characters"
            )
        if len(result.warnings) > configuration.max_warnings:
            raise TableStructureLimitError("warnings exceed max_warnings")
        TableStructureValidation._validate_retained_size(
            result, configuration.max_result_bytes
        )

    @staticmethod
    def _validate_structure_against_candidate(
        structure: TableStructure,
        candidate: TableCandidate,
        detection_result: TableDetectionResult,
    ) -> None:
        from .cell_validation import TableCellValidation
        from .column_validation import TableColumnValidation
        from .continuation_validation import TableContinuationValidation
        from .row_validation import TableRowValidation

        regions = candidate.regions
        blocks = tuple(
            block
            for page in detection_result.detection_input.document.pages
            for block in page.blocks
        )
        TableColumnValidation.create(structure=structure, regions=regions)
        TableRowValidation.create(structure=structure, regions=regions)
        TableCellValidation.create(
            structure=structure,
            regions=regions,
            blocks=blocks,
        )
        TableContinuationValidation.create(
            structure=structure,
            candidate=candidate,
        )

    @staticmethod
    def _preflight_result(
        structure_input: TableStructureRequest,
        structures: tuple[TableStructure, ...],
        warnings: tuple[IngestionWarning, ...],
        processor_name: str,
        processor_version: str,
    ) -> None:
        from projectkoios.ingestion.tables.structure.request import (
            TableStructureRequest,
        )
        from projectkoios.ingestion.tables.structure.structure import (
            TableStructure,
        )

        if not isinstance(structure_input, TableStructureRequest):
            raise TypeError("structure_input must be TableStructureRequest")
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
        TableStructureValidation._validate_identity_fields(
            processor_name, processor_version
        )

    @staticmethod
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
