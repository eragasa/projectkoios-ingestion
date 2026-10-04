"""OCRNativeTextBlockReference OCR domain object."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.ocr import _primitives as primitives


@dataclass(frozen=True)
class OCRNativeTextBlockReference(AbstractImmutableDataObject):
    """A source/page-linked reference to verified native text evidence."""

    block_id: str
    source_id: str
    source_blob_id: str
    page_index: int

    def __post_init__(self) -> None:
        for name, value in (
            ("block_id", self.block_id),
            ("source_id", self.source_id),
            ("source_blob_id", self.source_blob_id),
        ):
            primitives._hard_bounded_string(name, value, nonempty=True)
        primitives._nonnegative_integer("page_index", self.page_index)

    def identity_parts(self) -> tuple[object, ...]:
        return (
            self.block_id,
            self.source_id,
            self.source_blob_id,
            self.page_index,
        )
