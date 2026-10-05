"""One explicitly selected page in a selective OCR plan."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject


@dataclass(frozen=True, slots=True)
class SelectiveOCRPage(AbstractImmutableDataObject):
    """Zero-based page index selected for local OCR."""

    page_index: int

    def __post_init__(self) -> None:
        if isinstance(self.page_index, bool) or not isinstance(
            self.page_index,
            int,
        ):
            raise TypeError("selective OCR page index must be an integer")
        if self.page_index < 0:
            raise ValueError("selective OCR page index must be nonnegative")

    @classmethod
    def from_dict(cls, value: object) -> SelectiveOCRPage:
        if not isinstance(value, dict) or set(value) != {"page_index"}:
            raise ValueError("selective OCR page must contain only page_index")
        page_index = value["page_index"]
        if type(page_index) is not int:
            raise TypeError("selective OCR page index must be an integer")
        return cls(page_index=page_index)
