"""Immutable request for category-admitted COCO formula projection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.actionizer.request import (
    ConfigurableDataObjectActionRequest,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.admission.outcome import (
    CocoLayoutCategoryAdmission,
    CocoLayoutCategoryAdmissionStatus,
)
from projectkoios.ingestion.integrations.coco.layout.admission.result import (
    CocoLayoutRegionAdmissionResult,
)
from projectkoios.ingestion.layout.proposal.kind import LayoutRegionKind
from projectkoios.ingestion.models import ExtractedDocument

from .configuration import CocoLayoutEquationProjectionConfiguration


@dataclass(frozen=True, slots=True)
class CocoLayoutEquationProjectionRequest(
    ConfigurableDataObjectActionRequest[
        CocoLayoutEquationProjectionConfiguration
    ]
):
    """Bind one admitted formula category to its exact source document."""

    CONTRACT_NAME: ClassVar[str] = "coco-layout-equation-projection-request"
    CONTRACT_VERSION: ClassVar[str] = "2.0"

    document: ExtractedDocument
    admission_result: CocoLayoutRegionAdmissionResult
    configuration: CocoLayoutEquationProjectionConfiguration
    request_id: str = field(init=False)

    @property
    def formula_admission(self) -> CocoLayoutCategoryAdmission:
        """Return the unique admitted equation category outcome."""
        profile = self.admission_result.request.configuration.profile
        categories = tuple(
            category
            for category in profile.categories
            if category.kind is LayoutRegionKind.EQUATION
        )
        if len(categories) != 1:
            raise ValueError(
                "equation projection requires one formula category"
            )
        return self.admission_result.require_category(categories[0].category_id)

    def __post_init__(self) -> None:
        if type(self.document) is not ExtractedDocument:
            raise TypeError("document must be ExtractedDocument")
        if type(self.admission_result) is not CocoLayoutRegionAdmissionResult:
            raise TypeError(
                "admission_result must be CocoLayoutRegionAdmissionResult"
            )
        if (
            self.formula_admission.status
            is not CocoLayoutCategoryAdmissionStatus.ADMITTED
        ):
            raise ValueError(
                "equation projection requires an admitted formula category"
            )
        if type(self.configuration) is not (
            CocoLayoutEquationProjectionConfiguration
        ):
            raise TypeError("configuration must be a projection configuration")
        detector_request = self.admission_result.request.detector_result.request
        render = detector_request.render
        source = self.document.source
        if (
            render.source_id != source.source_id
            or render.source_blob_id != source.blob_id
        ):
            raise ValueError("admission result identifies another source")
        pages = tuple(
            page
            for page in self.document.pages
            if page.page_index == render.page_index
        )
        if len(pages) != 1:
            raise ValueError("admission page is absent from the exact document")
        page = pages[0]
        mapping = render.mapping
        page_box = (0.0, 0.0, page.width, page.height)
        effective_box = mapping.effective_source_bounding_box
        effective_contains_page = (
            effective_box[0] <= page_box[0]
            and effective_box[1] <= page_box[1]
            and effective_box[2] >= page_box[2]
            and effective_box[3] >= page_box[3]
        )
        if (
            mapping.source_coordinate_system != page.coordinate_system
            or mapping.page_rotation_degrees != page.rotation_degrees
            or mapping.requested_source_bounding_box != page_box
            or not effective_contains_page
        ):
            raise ValueError(
                "admission render mapping differs from the document page"
            )
        object.__setattr__(
            self,
            "request_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                self.document.document_id,
                source.source_id,
                source.blob_id,
                source.content_hash,
                self.admission_result.result_id,
                self.formula_admission.outcome_id,
                self.configuration.configuration_id,
            ),
        )
