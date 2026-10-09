"""Lineage-bound equation candidates projected from COCO proposals."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.adaptation import (
    CocoLayoutProposalAdaptation,
)
from projectkoios.ingestion.layout.proposal.kind import LayoutRegionKind
from projectkoios.ingestion.layout.render.evidence import (
    LayoutPageRenderEvidence,
)
from projectkoios.ingestion.layout.render.mapping import LayoutBoundingBox
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation
from projectkoios.ingestion.models import SourceSpan
from projectkoios.ingestion.sha256.hash import SHA256Hash

from .configuration import MAX_COCO_LAYOUT_EQUATION_CANDIDATES


@dataclass(frozen=True, slots=True)
class CocoLayoutEquationCandidateEvidence(AbstractImmutableDataObject):
    """Bind one admitted formula proposal to exact source-page geometry."""

    projection_request_id: str
    admission_result_id: str
    document_id: str
    source_content_hash: str
    render: LayoutPageRenderEvidence
    detection_id: str
    pixel_bounding_box: LayoutBoundingBox
    mapped_source_bounding_box: LayoutBoundingBox
    adaptation: CocoLayoutProposalAdaptation
    source_span: SourceSpan
    candidate_id: str = field(init=False)

    def __post_init__(self) -> None:
        request_id = LayoutValueValidation.require_text(
            "projection_request_id", self.projection_request_id
        )
        admission_id = LayoutValueValidation.require_text(
            "admission_result_id", self.admission_result_id
        )
        document_id = LayoutValueValidation.require_text(
            "document_id", self.document_id
        )
        digest = LayoutValueValidation.require_text(
            "source_content_hash", self.source_content_hash
        )
        if not SHA256Hash.is_canonical(digest):
            raise ValueError("source_content_hash must be a canonical SHA-256")
        if type(self.render) is not LayoutPageRenderEvidence:
            raise TypeError("render must be LayoutPageRenderEvidence")
        detection_id = LayoutValueValidation.require_text(
            "detection_id", self.detection_id
        )
        pixel_box = LayoutValueValidation.require_box(
            "pixel_bounding_box", self.pixel_bounding_box
        )
        mapped_box = LayoutValueValidation.require_box(
            "mapped_source_bounding_box", self.mapped_source_bounding_box
        )
        if type(self.adaptation) is not CocoLayoutProposalAdaptation:
            raise TypeError("adaptation must be CocoLayoutProposalAdaptation")
        if self.adaptation.proposal.kind is not LayoutRegionKind.EQUATION:
            raise ValueError("equation candidate requires a formula proposal")
        if detection_id != self.adaptation.detection.detection_id:
            raise ValueError("candidate detection identity differs")
        if (
            pixel_box != self.adaptation.detection.bounding_box_pixels
            or pixel_box != self.adaptation.proposal.bounding_box_pixels
        ):
            raise ValueError("candidate pixel geometry differs")
        if mapped_box != self.render.mapping.pixel_box_to_source_box(pixel_box):
            raise ValueError("candidate source mapping differs")
        if type(self.source_span) is not SourceSpan:
            raise TypeError("source_span must be SourceSpan")
        if self.source_span.bounding_box is None:
            raise ValueError("equation candidate requires source geometry")
        if (
            self.render.source_id != self.source_span.source_id
            or self.render.source_blob_id != self.source_span.source_blob_id
            or self.render.page_index != self.source_span.page_index
        ):
            raise ValueError("candidate render and source span differ")
        if (
            self.source_span.source_object_id
            != self.adaptation.proposal.proposal_id
        ):
            raise ValueError(
                "equation candidate source object must identify its proposal"
            )
        object.__setattr__(self, "pixel_bounding_box", pixel_box)
        object.__setattr__(self, "mapped_source_bounding_box", mapped_box)
        object.__setattr__(
            self,
            "candidate_id",
            stable_id(
                "coco-layout-equation-candidate-evidence",
                request_id,
                admission_id,
                document_id,
                digest,
                self.render.render_id,
                self.render.mapping.mapping_id,
                detection_id,
                pixel_box,
                mapped_box,
                self.adaptation.adaptation_id,
                self.source_span.identity_parts(),
            ),
        )


@dataclass(frozen=True, slots=True, init=False)
class CocoLayoutEquationCandidateEvidenceInventory:
    """Own canonical source-ordered formula candidate evidence."""

    _candidates: tuple[CocoLayoutEquationCandidateEvidence, ...] = field(
        repr=True
    )
    inventory_id: str = field(init=False)

    def __init__(
        self, *candidates: CocoLayoutEquationCandidateEvidence
    ) -> None:
        values = tuple(candidates)
        if len(values) > MAX_COCO_LAYOUT_EQUATION_CANDIDATES:
            raise ValueError(
                "equation candidates exceed the implementation limit"
            )
        if any(
            type(value) is not CocoLayoutEquationCandidateEvidence
            for value in values
        ):
            raise TypeError(
                "candidate inventory requires exact candidate evidence"
            )
        identities = tuple(value.candidate_id for value in values)
        if len(identities) != len(set(identities)):
            raise ValueError("equation candidate identities must be unique")
        order = tuple(
            (
                value.source_span.page_index,
                value.source_span.bounding_box[1],
                value.source_span.bounding_box[0],
                value.source_span.bounding_box[3],
                value.source_span.bounding_box[2],
                value.candidate_id,
            )
            for value in values
            if value.source_span.bounding_box is not None
        )
        if order != tuple(sorted(order)):
            raise ValueError(
                "equation candidates must use canonical source order"
            )
        object.__setattr__(self, "_candidates", values)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id("coco-layout-equation-candidate-inventory", identities),
        )

    def __iter__(self) -> Iterator[CocoLayoutEquationCandidateEvidence]:
        return iter(self._candidates)

    def __len__(self) -> int:
        return len(self._candidates)
