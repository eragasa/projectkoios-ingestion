"""OCRNativeBlockEvidence reconciliation domain object."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import (
    BoundingBox,
    ExtractedBlock,
    SourceSpan,
)
from projectkoios.ingestion.reconciliation import _geometry as geometry
from projectkoios.ingestion.reconciliation import _identity as identity
from projectkoios.ingestion.reconciliation import _primitives as primitives
from projectkoios.ingestion.reconciliation._limits import (
    _MAX_SOURCE_SPANS_PER_BLOCK,
)
from projectkoios.ingestion.reconciliation.constants import (
    OCR_RECONCILIATION_CONTRACT_VERSION,
)
from projectkoios.ingestion.reconciliation.limit_error import (
    OCRReconciliationLimitError,
)


@dataclass(frozen=True)
class OCRNativeBlockEvidence(AbstractImmutableDataObject):
    """One exact selected native text block in layout-proposed order."""

    evidence_id: str
    block_id: str
    text: str
    source_spans: tuple[SourceSpan, ...]
    order: int

    @classmethod
    def from_block(
        cls, block: ExtractedBlock, *, order: int
    ) -> OCRNativeBlockEvidence:
        if block.kind != "text" or not isinstance(block.text, str):
            raise ValueError("native reconciliation evidence must contain text")
        primitives._bounded_string("native block ID", block.block_id)
        primitives._bounded_text("native block text", block.text)
        primitives._require_tuple("native source spans", block.source_spans)
        if len(block.source_spans) > _MAX_SOURCE_SPANS_PER_BLOCK:
            raise OCRReconciliationLimitError(
                "native source spans exceed the implementation maximum"
            )
        primitives._nonnegative_integer("native block order", order)
        evidence_id = identity._native_block_evidence_id(block, order)
        return cls(
            evidence_id=evidence_id,
            block_id=block.block_id,
            text=block.text,
            source_spans=block.source_spans,
            order=order,
        )

    def __post_init__(self) -> None:
        primitives._bounded_string("native evidence ID", self.evidence_id)
        primitives._bounded_string("native block ID", self.block_id)
        primitives._bounded_text("native block text", self.text)
        primitives._require_tuple("native source spans", self.source_spans)
        if not self.source_spans:
            raise ValueError("native block evidence requires source spans")
        if len(self.source_spans) > _MAX_SOURCE_SPANS_PER_BLOCK:
            raise OCRReconciliationLimitError(
                "native source spans exceed the implementation maximum"
            )
        if any(not isinstance(span, SourceSpan) for span in self.source_spans):
            raise TypeError(
                "native source spans must contain SourceSpan values"
            )
        primitives._nonnegative_integer("native block order", self.order)
        expected = stable_id(
            "ocr-native-block-evidence",
            OCR_RECONCILIATION_CONTRACT_VERSION,
            self.block_id,
            self.text,
            tuple(span.identity_parts() for span in self.source_spans),
            self.order,
        )
        if self.evidence_id != expected:
            raise ValueError("native block evidence ID is inconsistent")

    @property
    def bounding_box(self) -> BoundingBox | None:
        return geometry._spans_bounding_box(self.source_spans)
