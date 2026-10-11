"""Exact cross-bindings from page projection to sanitized evidence."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.page.projection.enrichment.basis import (
    PageProjectionEvidenceStyle,
)
from projectkoios.ingestion.page.projection.identity import (
    fingerprint_page_projection_identity,
)
from projectkoios.ingestion.page.projection.limits.definition import (
    PAGE_PROJECTION_LIMITS,
)


@dataclass(frozen=True, slots=True)
class PageProjectionEvidenceCrossBinding:
    """Bind one downstream key to exact source, page, block, and result IDs."""

    page_projection_result_id: str
    source_result_id: str
    reading_projection_result_id: str
    artifact_verification_result_id: str
    source_id: str
    document_id: str
    source_page_id: str
    page_location_id: str
    page_projection_page_id: str
    page_projection_block_id: str
    source_evidence_id: str
    style: PageProjectionEvidenceStyle
    binding_id: str = field(init=False)

    def __post_init__(self) -> None:
        material: dict[str, str] = {}
        for name, value in (
            ("page_projection_result_id", self.page_projection_result_id),
            ("source_result_id", self.source_result_id),
            ("reading_projection_result_id", self.reading_projection_result_id),
            (
                "artifact_verification_result_id",
                self.artifact_verification_result_id,
            ),
            ("source_id", self.source_id),
            ("document_id", self.document_id),
            ("source_page_id", self.source_page_id),
            ("page_location_id", self.page_location_id),
            ("page_projection_page_id", self.page_projection_page_id),
            ("page_projection_block_id", self.page_projection_block_id),
            ("source_evidence_id", self.source_evidence_id),
        ):
            material[name] = PAGE_PROJECTION_LIMITS.require_identity(
                value, name
            )
        if not isinstance(self.style, PageProjectionEvidenceStyle):
            raise TypeError("style must be PageProjectionEvidenceStyle")
        material["style"] = self.style.value
        object.__setattr__(
            self,
            "binding_id",
            fingerprint_page_projection_identity(
                namespace="page-projection-evidence-cross-binding",
                material=material,
            ),
        )
