"""Exact requests for projecting resolved layout into a COCO sidecar record."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.document import (
    CocoLayoutAnnotationDocument,
)
from projectkoios.ingestion.integrations.coco.layout.json.annotations import (
    CocoLayoutAnnotationsJsonContract,
)
from projectkoios.ingestion.integrations.coco.layout.lineage import (
    CocoLayoutLineageDocument,
)
from projectkoios.ingestion.layout.reading.order.kind import (
    LayoutReadingOrderStatus,
)
from projectkoios.ingestion.layout.reading.order.result import (
    LayoutReadingOrderResult,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter


@dataclass(frozen=True, slots=True)
class CocoLayoutReadingOrderProjectionRequest(DataObjectActionRequest):
    """Bind exact annotations, lineage, and one resolved image layout."""

    annotations: CocoLayoutAnnotationDocument
    lineage: CocoLayoutLineageDocument
    layout_result: LayoutReadingOrderResult
    image_id: int
    request_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.annotations) is not CocoLayoutAnnotationDocument:
            raise TypeError("annotations must be CocoLayoutAnnotationDocument")
        if type(self.lineage) is not CocoLayoutLineageDocument:
            raise TypeError("lineage must be CocoLayoutLineageDocument")
        if type(self.layout_result) is not LayoutReadingOrderResult:
            raise TypeError("layout_result must be LayoutReadingOrderResult")
        if type(self.image_id) is not int or self.image_id < 1:
            raise ValueError("image_id must be a positive integer")
        if self.lineage.profile_id != self.annotations.profile.profile_id:
            raise ValueError("COCO lineage profile differs from annotations")
        if (
            self.layout_result.request.upstream_evidence_id
            != self.lineage.document_id
        ):
            raise ValueError(
                "resolved upstream lineage differs from COCO lineage document"
            )
        annotations_sha256 = SHA256Fingerprinter.fingerprint(
            content=CocoLayoutAnnotationsJsonContract().serialize_bytes(
                self.annotations
            )
        )
        if self.lineage.annotations_sha256 != annotations_sha256:
            raise ValueError("COCO lineage digest differs from annotations")
        detections = tuple(self.annotations.detections)
        entries = tuple(self.lineage.entries)
        if len(detections) != len(entries):
            raise ValueError("COCO lineage must cover every annotation")
        for detection, entry in zip(detections, entries, strict=True):
            if (
                detection.annotation_id != entry.annotation_id
                or detection.detection_id != entry.detection_id
            ):
                raise ValueError("COCO lineage differs from annotations")
        image = self.annotations.images.require(self.image_id)
        render = self.layout_result.request.render
        if (
            image.render_id != render.render_id
            or image.width != render.image_width
            or image.height != render.image_height
            or image.image_media_type != render.image_media_type
            or image.image_sha256 != render.image_sha256
        ):
            raise ValueError("resolved layout differs from the COCO image")
        if (
            self.layout_result.status is not LayoutReadingOrderStatus.RESOLVED
            or self.layout_result.resolution is None
        ):
            raise ValueError(
                "COCO projection requires resolved layout evidence"
            )
        object.__setattr__(
            self,
            "request_id",
            stable_id(
                "coco-layout-reading-order-projection-request",
                self.annotations.document_id,
                self.lineage.document_id,
                self.layout_result.result_id,
                self.image_id,
            ),
        )
