"""Immutable plan for bounded selective OCR reconciliation."""

from __future__ import annotations

import json
from dataclasses import dataclass

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.ocr.reconciliation.batch.item import (
    SelectiveOCRReconciliationItem,
)

_MAX_ITEMS = 256
_MAX_TOTAL_PAGES = 1_024


@dataclass(frozen=True, slots=True)
class SelectiveOCRReconciliationPlan(AbstractImmutableDataObject):
    """Exact extraction and OCR publications authorized for reconciliation."""

    schema_version: int
    items: tuple[SelectiveOCRReconciliationItem, ...]

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("unsupported reconciliation plan schema version")
        if type(self.items) is not tuple or not self.items:
            raise ValueError("reconciliation plan must contain an item tuple")
        if len(self.items) > _MAX_ITEMS:
            raise ValueError("reconciliation plan exceeds its item limit")
        if any(
            type(item) is not SelectiveOCRReconciliationItem
            for item in self.items
        ):
            raise TypeError("reconciliation plan items must be typed")
        if sum(len(item.pages) for item in self.items) > _MAX_TOTAL_PAGES:
            raise ValueError("reconciliation plan exceeds its total page limit")
        for name, values in (
            ("source IDs", tuple(item.source.source_id for item in self.items)),
            (
                "source PDF paths",
                tuple(item.source.pdf_path.as_posix() for item in self.items),
            ),
            (
                "ingestion directories",
                tuple(
                    item.source.output_directory.as_posix()
                    for item in self.items
                ),
            ),
            (
                "OCR directories",
                tuple(item.ocr_directory.as_posix() for item in self.items),
            ),
            (
                "output directories",
                tuple(item.output_directory.as_posix() for item in self.items),
            ),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"reconciliation plan has duplicate {name}")

    @classmethod
    def from_json(cls, text: str) -> SelectiveOCRReconciliationPlan:
        value = json.loads(text)
        if type(value) is not dict or set(value) != {"schema_version", "items"}:
            raise ValueError("reconciliation plan has an invalid shape")
        schema_version = value["schema_version"]
        items = value["items"]
        if type(schema_version) is not int:
            raise TypeError("schema_version must be an integer")
        if type(items) is not list:
            raise TypeError("items must be an array")
        return cls(
            schema_version=schema_version,
            items=tuple(
                SelectiveOCRReconciliationItem.from_dict(item) for item in items
            ),
        )

    def to_json(self) -> str:
        return (
            json.dumps(
                {
                    "schema_version": self.schema_version,
                    "items": [_item_value(item) for item in self.items],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )


def _item_value(item: SelectiveOCRReconciliationItem) -> dict[str, object]:
    return {
        "source": {
            "source_id": item.source.source_id,
            "pdf_path": item.source.pdf_path.as_posix(),
            "output_directory": item.source.output_directory.as_posix(),
            "sha256": item.source.sha256,
            "byte_size": item.source.byte_size,
            "locator": item.source.locator,
        },
        "extraction_sha256": item.extraction_sha256,
        "ocr_directory": item.ocr_directory.as_posix(),
        "output_directory": item.output_directory.as_posix(),
        "pages": [
            {
                "page_index": page.page_index,
                "ocr_publication_sha256": page.ocr_publication_sha256,
            }
            for page in item.pages
        ],
    }
