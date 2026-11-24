"""Typed binding to one exact unaccepted table transcription proposal."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.tables.acceptance.cell import (
    TableEvidenceProposalCell,
)
from projectkoios.ingestion.tables.acceptance.parameter import (
    TableEvidenceParameter,
)
from projectkoios.ingestion.tables.acceptance.row import (
    TableEvidenceProposalRow,
)
from projectkoios.ingestion.tables.acceptance.validation import (
    require_box,
    require_column_index,
    require_id,
    require_positive,
    require_row_index,
    require_sha256,
    require_text,
)


@dataclass(frozen=True, slots=True)
class TableEvidenceProposal(AbstractImmutableDataObject):
    """Retain complete ordered cells from an exact private proposal artifact."""

    CONTRACT_NAME: ClassVar[str] = "table-evidence-proposal"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    proposal_sha256: str
    source_id: str
    source_blob_id: str
    source_sha256: str
    source_byte_length: int
    source_media_type: str
    rights_access_status: str
    physical_page_index: int
    physical_page_number: int
    printed_page_label: str
    reading_page_location_id: str
    rendered_region_id: str
    rendered_region_sha256: str
    source_bounding_box: tuple[float, float, float, float]
    coordinate_system: str
    resolution_dpi: int
    parameters: tuple[TableEvidenceParameter, ...]
    rows: tuple[TableEvidenceProposalRow, ...]
    proposal_id: str = field(init=False)
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported table-evidence proposal contract")
        require_sha256("proposal_sha256", self.proposal_sha256)
        require_text("source_id", self.source_id, identity=True)
        require_id("source_blob_id", self.source_blob_id, "blob")
        require_sha256("source_sha256", self.source_sha256)
        if self.source_blob_id != f"blob:sha256:{self.source_sha256}":
            raise ValueError("source blob and SHA-256 disagree")
        require_positive(
            "source_byte_length", self.source_byte_length, maximum=1_000_000_000
        )
        require_text("source_media_type", self.source_media_type, identity=True)
        require_text(
            "rights_access_status", self.rights_access_status, identity=True
        )
        require_row_index("physical_page_index", self.physical_page_index)
        if self.physical_page_number != self.physical_page_index + 1:
            raise ValueError("physical page number and index disagree")
        require_text(
            "printed_page_label", self.printed_page_label, identity=True
        )
        require_id(
            "reading_page_location_id",
            self.reading_page_location_id,
            "reading-page-location",
        )
        require_id(
            "rendered_region_id", self.rendered_region_id, "rendered-region"
        )
        require_sha256("rendered_region_sha256", self.rendered_region_sha256)
        object.__setattr__(
            self,
            "source_bounding_box",
            require_box("source_bounding_box", self.source_bounding_box),
        )
        require_text("coordinate_system", self.coordinate_system, identity=True)
        require_positive("resolution_dpi", self.resolution_dpi, maximum=9_600)
        if not isinstance(self.parameters, tuple) or not self.parameters:
            raise ValueError("parameters must be a non-empty immutable tuple")
        if any(
            type(parameter) is not TableEvidenceParameter
            for parameter in self.parameters
        ):
            raise TypeError("parameters contain an unsupported value")
        if tuple(
            parameter.parameter_index for parameter in self.parameters
        ) != tuple(range(len(self.parameters))):
            raise ValueError("parameters must have contiguous order")
        keys = tuple(parameter.parameter_key for parameter in self.parameters)
        headers = tuple(
            parameter.printed_header for parameter in self.parameters
        )
        if len(set(keys)) != len(keys) or len(set(headers)) != len(headers):
            raise ValueError(
                "parameter keys and printed headers must be unique"
            )
        if len({parameter.unit for parameter in self.parameters}) != 1:
            raise ValueError("all table parameters must share one unit")
        if tuple(
            sorted(parameter.printed_panel for parameter in self.parameters)
        ) != tuple(parameter.printed_panel for parameter in self.parameters):
            raise ValueError("printed panels must preserve parameter order")
        if not isinstance(self.rows, tuple) or not self.rows:
            raise ValueError("rows must be a non-empty immutable tuple")
        if any(type(row) is not TableEvidenceProposalRow for row in self.rows):
            raise TypeError("rows contain an unsupported value")
        if tuple(row.row_index for row in self.rows) != tuple(
            range(len(self.rows))
        ):
            raise ValueError("rows must have contiguous order")
        compounds = tuple(row.compound for row in self.rows)
        if len(set(compounds)) != len(compounds):
            raise ValueError("compound labels must be unique")
        for row in self.rows:
            if len(row.cells) != len(self.parameters):
                raise ValueError("every row must cover every parameter")
            for cell, parameter in zip(row.cells, self.parameters, strict=True):
                if (
                    cell.parameter_key != parameter.parameter_key
                    or cell.printed_header != parameter.printed_header
                    or cell.unit != parameter.unit
                    or cell.printed_panel != parameter.printed_panel
                ):
                    raise ValueError("cell and parameter definitions disagree")
                x0, y0, x1, y1 = cell.source_bounding_box
                bx0, by0, bx1, by1 = self.source_bounding_box
                if x0 < bx0 or y0 < by0 or x1 > bx1 or y1 > by1:
                    raise ValueError("cell geometry falls outside table region")
        object.__setattr__(
            self,
            "proposal_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                self.proposal_sha256,
                self.source_id,
                self.source_blob_id,
                self.source_sha256,
                self.source_byte_length,
                self.source_media_type,
                self.rights_access_status,
                self.physical_page_index,
                self.physical_page_number,
                self.printed_page_label,
                self.reading_page_location_id,
                self.rendered_region_id,
                self.rendered_region_sha256,
                self.source_bounding_box,
                self.coordinate_system,
                self.resolution_dpi,
                tuple(parameter.parameter_id for parameter in self.parameters),
                tuple(row.row_id for row in self.rows),
            ),
        )
        require_id("proposal_id", self.proposal_id, self.CONTRACT_NAME)

    @property
    def cell_count(self) -> int:
        return sum(len(row.cells) for row in self.rows)

    def cell_by_coordinate(
        self, row_index: int, parameter_index: int
    ) -> TableEvidenceProposalCell:
        require_row_index("row_index", row_index)
        if row_index >= len(self.rows):
            raise ValueError("row index is outside the proposal")
        require_column_index("parameter_index", parameter_index)
        if parameter_index >= len(self.parameters):
            raise ValueError("parameter index is outside the proposal")
        return self.rows[row_index].cells[parameter_index]
