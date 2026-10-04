"""Source-backed geometry used during table-structure derivation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.models import BoundingBox, ExtractedBlock
from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.constants import (
    TABLE_STRUCTURE_CONTRACT_VERSION,
)


@dataclass(frozen=True)
class TableSourceRecord(AbstractTableStructureDataObject):
    """Retain one source block with validated geometry and source order."""

    CONTRACT_NAME: ClassVar[str] = "table-source-record"
    CONTRACT_VERSION: ClassVar[str] = TABLE_STRUCTURE_CONTRACT_VERSION

    block: ExtractedBlock
    box: BoundingBox
    order: int

    def __post_init__(self) -> None:
        if not isinstance(self.block, ExtractedBlock):
            raise TypeError("source record block must be ExtractedBlock")
        object.__setattr__(self, "box", self._validate_box(self.box))
        self._validate_nonnegative_integer("source record order", self.order)

    @classmethod
    def from_block(cls, block: ExtractedBlock, order: int) -> TableSourceRecord:
        boxes = tuple(
            span.bounding_box
            for span in block.source_spans
            if span.bounding_box is not None
        )
        if not boxes:
            raise ValueError("table source block lacks geometry")
        return cls(
            block=block,
            box=cls._validate_box(
                (
                    min(box[0] for box in boxes),
                    min(box[1] for box in boxes),
                    max(box[2] for box in boxes),
                    max(box[3] for box in boxes),
                )
            ),
            order=order,
        )

    @classmethod
    def cluster_rows(
        cls,
        records: tuple[TableSourceRecord, ...],
        tolerance: float,
    ) -> tuple[tuple[TableSourceRecord, ...], ...]:
        rows: list[list[TableSourceRecord]] = []
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

    @staticmethod
    def cluster_values(
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

    @staticmethod
    def column_for(center_x: float, boundaries: tuple[float, ...]) -> int:
        for index, (left, right) in enumerate(
            zip(boundaries, boundaries[1:], strict=False)
        ):
            if left <= center_x <= right:
                return index
        return len(boundaries) - 2

    @staticmethod
    def normalized_text(value: str) -> str:
        return " ".join(value.casefold().split())

    @property
    def center_x(self) -> float:
        return (self.box[0] + self.box[2]) / 2.0

    @property
    def center_y(self) -> float:
        return (self.box[1] + self.box[3]) / 2.0
