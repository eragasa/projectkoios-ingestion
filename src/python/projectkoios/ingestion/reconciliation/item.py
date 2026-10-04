"""OCRReconciledItem reconciliation domain object."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.reconciliation import _identity as identity
from projectkoios.ingestion.reconciliation import _primitives as primitives
from projectkoios.ingestion.reconciliation.item_kind import (
    OCRReconciledItemKind,
)


@dataclass(frozen=True)
class OCRReconciledItem(AbstractImmutableDataObject):
    item_id: str
    kind: OCRReconciledItemKind
    order: int
    native_segment_id: str | None
    ocr_line_id: str | None
    proposed_text: str | None
    warning_ids: tuple[str, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        kind: OCRReconciledItemKind,
        order: int,
        native_segment_id: str | None,
        ocr_line_id: str | None,
        proposed_text: str | None,
        warning_ids: tuple[str, ...] = (),
    ) -> OCRReconciledItem:
        if not isinstance(kind, OCRReconciledItemKind):
            raise ValueError("reconciled item kind is unsupported")
        primitives._nonnegative_integer("reconciled item order", order)
        for name, value in (
            ("native_segment_id", native_segment_id),
            ("ocr_line_id", ocr_line_id),
        ):
            if value is not None:
                primitives._bounded_string(name, value)
        if proposed_text is not None:
            primitives._bounded_text(
                "proposed text", proposed_text, nonempty=True
            )
        primitives._require_unique_strings("item warning IDs", warning_ids)
        item_id = identity._item_id(
            kind,
            order,
            native_segment_id,
            ocr_line_id,
            proposed_text,
            warning_ids,
        )
        return cls(
            item_id=item_id,
            kind=kind,
            order=order,
            native_segment_id=native_segment_id,
            ocr_line_id=ocr_line_id,
            proposed_text=proposed_text,
            warning_ids=warning_ids,
        )

    def __post_init__(self) -> None:
        primitives._bounded_string("reconciled item ID", self.item_id)
        if not isinstance(self.kind, OCRReconciledItemKind):
            raise ValueError("reconciled item kind is unsupported")
        primitives._nonnegative_integer("reconciled item order", self.order)
        for name, value in (
            ("native_segment_id", self.native_segment_id),
            ("ocr_line_id", self.ocr_line_id),
        ):
            if value is not None:
                primitives._bounded_string(name, value)
        if self.proposed_text is not None:
            primitives._bounded_text(
                "proposed text", self.proposed_text, nonempty=True
            )
        primitives._require_unique_strings("item warning IDs", self.warning_ids)
        if self.kind is OCRReconciledItemKind.DUPLICATE:
            if (
                self.native_segment_id is None
                or self.ocr_line_id is None
                or self.proposed_text is None
                or self.warning_ids
            ):
                raise ValueError("duplicate item evidence is incomplete")
        elif self.kind is OCRReconciledItemKind.DISAGREEMENT:
            if (
                self.native_segment_id is None
                or self.ocr_line_id is None
                or self.proposed_text is not None
                or not self.warning_ids
            ):
                raise ValueError("disagreement item evidence is incomplete")
        elif self.kind is OCRReconciledItemKind.NATIVE_ONLY:
            if (
                self.native_segment_id is None
                or self.ocr_line_id is not None
                or self.proposed_text is None
            ):
                raise ValueError("native-only item evidence is inconsistent")
        elif (
            self.native_segment_id is not None
            or self.ocr_line_id is None
            or self.proposed_text is None
        ):
            raise ValueError("OCR-only item evidence is inconsistent")
        expected = identity._item_id(
            self.kind,
            self.order,
            self.native_segment_id,
            self.ocr_line_id,
            self.proposed_text,
            self.warning_ids,
        )
        if self.item_id != expected:
            raise ValueError("reconciled item ID is inconsistent")
