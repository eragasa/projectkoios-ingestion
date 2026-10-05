"""OCRNativeLineSegment reconciliation domain object."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.models import BoundingBox
from projectkoios.ingestion.reconciliation import _geometry as geometry
from projectkoios.ingestion.reconciliation import _identity as identity
from projectkoios.ingestion.reconciliation import _primitives as primitives
from projectkoios.ingestion.reconciliation.native_block_evidence import (
    OCRNativeBlockEvidence,
)


@dataclass(frozen=True)
class OCRNativeLineSegment(AbstractImmutableDataObject):
    """A source-backed text line projected from one native block payload."""

    segment_id: str
    block_evidence_id: str
    block_id: str
    line_index: int
    text: str
    normalized_text: str
    source_bounding_box: BoundingBox | None
    order: int

    @classmethod
    def create(
        cls,
        *,
        block: OCRNativeBlockEvidence,
        line_index: int,
        text: str,
        order: int,
    ) -> OCRNativeLineSegment:
        if not isinstance(block, OCRNativeBlockEvidence):
            raise TypeError("block must be OCRNativeBlockEvidence")
        primitives._nonnegative_integer("line_index", line_index)
        primitives._nonnegative_integer("segment order", order)
        primitives._bounded_text("native segment text", text, nonempty=True)
        normalized = geometry._normalized_text(text)
        bounding_box = block.bounding_box
        segment_id = identity._native_segment_id(
            block.evidence_id,
            block.block_id,
            line_index,
            text,
            normalized,
            bounding_box,
            order,
        )
        return cls(
            segment_id=segment_id,
            block_evidence_id=block.evidence_id,
            block_id=block.block_id,
            line_index=line_index,
            text=text,
            normalized_text=normalized,
            source_bounding_box=bounding_box,
            order=order,
        )

    def __post_init__(self) -> None:
        for name, value in (
            ("segment_id", self.segment_id),
            ("block_evidence_id", self.block_evidence_id),
            ("block_id", self.block_id),
        ):
            primitives._bounded_string(name, value)
        primitives._nonnegative_integer("line_index", self.line_index)
        primitives._nonnegative_integer("segment order", self.order)
        primitives._bounded_text(
            "native segment text", self.text, nonempty=True
        )
        expected_normalized = geometry._normalized_text(self.text)
        if not expected_normalized:
            raise ValueError("native segment text must contain visible text")
        if self.normalized_text != expected_normalized:
            raise ValueError("native segment normalized text is inconsistent")
        if self.source_bounding_box is not None:
            object.__setattr__(
                self,
                "source_bounding_box",
                geometry._validated_box(self.source_bounding_box),
            )
        expected = identity._native_segment_id(
            self.block_evidence_id,
            self.block_id,
            self.line_index,
            self.text,
            self.normalized_text,
            self.source_bounding_box,
            self.order,
        )
        if self.segment_id != expected:
            raise ValueError("native segment ID is inconsistent")
