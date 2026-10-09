"""Pinned optional Docling rule-based reading-order provider."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version

from projectkoios.ingestion.layout.proposal.kind import LayoutRegionKind
from projectkoios.ingestion.layout.reading.order.kind import (
    LayoutReadingDirection,
)
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation

from .configuration import (
    DOCLING_READING_ORDER_ALGORITHM,
    DOCLING_READING_ORDER_CORE_PACKAGE_NAME,
    DOCLING_READING_ORDER_CORE_PACKAGE_VERSION,
    DOCLING_READING_ORDER_PACKAGE_NAME,
    DOCLING_READING_ORDER_PACKAGE_VERSION,
    DOCLING_READING_ORDER_RTREE_PACKAGE_NAME,
    DOCLING_READING_ORDER_RTREE_PACKAGE_VERSION,
)
from .kind import DoclingReadingOrderFailureKind
from .request import DoclingReadingOrderRequest


@dataclass(slots=True)
class DoclingReadingOrderProviderError(Exception):
    """Expose a closed provider failure without leaking vendor exceptions."""

    kind: DoclingReadingOrderFailureKind
    code: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, DoclingReadingOrderFailureKind):
            raise TypeError("kind must be DoclingReadingOrderFailureKind")
        code = LayoutValueValidation.require_text("code", self.code)
        object.__setattr__(self, "code", code)
        Exception.__init__(self, code)


class DoclingReadingOrderProvider(ABC):
    """Generate one candidate from an exact immutable request."""

    @property
    @abstractmethod
    def implementation_id(self) -> str:
        """Return the pinned provider implementation identity."""

    @abstractmethod
    def order(self, *, request: DoclingReadingOrderRequest) -> object:
        """Return one candidate or raise a typed provider failure."""


class InstalledDoclingReadingOrderProvider(DoclingReadingOrderProvider):
    """Invoke the installed pinned Docling rule-based predictor."""

    __slots__ = ()

    @property
    def implementation_id(self) -> str:
        """Return package, dependency, and algorithm versions."""
        return (
            f"{DOCLING_READING_ORDER_PACKAGE_NAME}:"
            f"{DOCLING_READING_ORDER_PACKAGE_VERSION}/"
            f"{DOCLING_READING_ORDER_CORE_PACKAGE_NAME}:"
            f"{DOCLING_READING_ORDER_CORE_PACKAGE_VERSION}/"
            f"{DOCLING_READING_ORDER_RTREE_PACKAGE_NAME}:"
            f"{DOCLING_READING_ORDER_RTREE_PACKAGE_VERSION}/"
            f"{DOCLING_READING_ORDER_ALGORITHM}"
        )

    @staticmethod
    def verify_installed_versions() -> None:
        """Require every runtime package version pinned by configuration."""
        expected = (
            (
                DOCLING_READING_ORDER_PACKAGE_NAME,
                DOCLING_READING_ORDER_PACKAGE_VERSION,
            ),
            (
                DOCLING_READING_ORDER_CORE_PACKAGE_NAME,
                DOCLING_READING_ORDER_CORE_PACKAGE_VERSION,
            ),
            (
                DOCLING_READING_ORDER_RTREE_PACKAGE_NAME,
                DOCLING_READING_ORDER_RTREE_PACKAGE_VERSION,
            ),
        )
        try:
            actual = tuple((name, version(name)) for name, _ in expected)
        except PackageNotFoundError as error:
            raise DoclingReadingOrderProviderError(
                DoclingReadingOrderFailureKind.PROVIDER_UNAVAILABLE,
                "docling_reading_order_dependency_unavailable",
            ) from error
        if actual != expected:
            raise DoclingReadingOrderProviderError(
                DoclingReadingOrderFailureKind.PROVIDER_VERSION_MISMATCH,
                "docling_reading_order_dependency_version_mismatch",
            )

    @staticmethod
    def label_name_for(kind: LayoutRegionKind) -> str:
        """Map supported Koios kinds without silently coercing extensions."""
        names = {
            LayoutRegionKind.TEXT: "TEXT",
            LayoutRegionKind.TITLE: "TITLE",
            LayoutRegionKind.LIST: "LIST_ITEM",
            LayoutRegionKind.TABLE: "TABLE",
            LayoutRegionKind.FIGURE: "PICTURE",
            LayoutRegionKind.EQUATION: "FORMULA",
            LayoutRegionKind.HEADER: "PAGE_HEADER",
            LayoutRegionKind.FOOTER: "PAGE_FOOTER",
            LayoutRegionKind.FOOTNOTE: "FOOTNOTE",
            LayoutRegionKind.CAPTION: "CAPTION",
        }
        label_name = names.get(kind)
        if label_name is None:
            raise DoclingReadingOrderProviderError(
                DoclingReadingOrderFailureKind.UNSUPPORTED_REGION_KIND,
                "docling_reading_order_region_kind_unsupported",
            )
        return label_name

    def order(self, *, request: DoclingReadingOrderRequest) -> object:
        """Invoke Docling once and retain only the neutral ID permutation."""
        if type(request) is not DoclingReadingOrderRequest:
            raise TypeError("request must be DoclingReadingOrderRequest")
        if request.direction is not LayoutReadingDirection.LEFT_TO_RIGHT:
            raise DoclingReadingOrderProviderError(
                DoclingReadingOrderFailureKind.UNSUPPORTED_DIRECTION,
                "docling_reading_order_direction_unsupported",
            )
        self.verify_installed_versions()
        try:
            from docling.models.postprocessing.reading_order_rb import (
                PageElement,
                ReadingOrderPredictor,
            )
            from docling_core.types.doc import CoordOrigin, Size
            from docling_core.types.doc.labels import DocItemLabel
        except ImportError as error:
            raise DoclingReadingOrderProviderError(
                DoclingReadingOrderFailureKind.PROVIDER_UNAVAILABLE,
                "docling_reading_order_import_failed",
            ) from error
        page_size = Size(
            width=request.page_width_pixels,
            height=request.page_height_pixels,
        )
        element_by_index = {
            element.source_index: element for element in request.elements
        }
        try:
            vendor_elements = [
                PageElement(
                    cid=element.source_index,
                    page_no=1,
                    page_size=page_size,
                    label=DocItemLabel[self.label_name_for(element.kind)],
                    text="",
                    l=element.bounding_box_pixels[0],
                    t=element.bounding_box_pixels[1],
                    r=element.bounding_box_pixels[2],
                    b=element.bounding_box_pixels[3],
                    coord_origin=CoordOrigin.TOPLEFT,
                )
                for element in request.elements
            ]
            predicted = ReadingOrderPredictor().predict_reading_order(
                vendor_elements
            )
            if len(predicted) > request.configuration.maximum_elements:
                raise DoclingReadingOrderProviderError(
                    DoclingReadingOrderFailureKind.OUTPUT_ELEMENT_LIMIT_EXCEEDED,
                    "docling_reading_order_output_element_limit_exceeded",
                )
            element_ids = tuple(
                element_by_index[element.cid].region_id
                for element in predicted
            )
        except DoclingReadingOrderProviderError:
            raise
        except Exception as error:
            raise DoclingReadingOrderProviderError(
                DoclingReadingOrderFailureKind.PROVIDER_FAILURE,
                "docling_reading_order_prediction_failed",
            ) from error
        return element_ids
