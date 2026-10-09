"""Pinned Docling reading-order candidate configuration."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.base.actionizer.configuration import (
    AbstractActionConfiguration,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation

from .limits import MAX_DOCLING_READING_ORDER_ELEMENTS

DOCLING_READING_ORDER_PACKAGE_NAME = "docling-slim"
DOCLING_READING_ORDER_PACKAGE_VERSION = "2.135.0"
DOCLING_READING_ORDER_CORE_PACKAGE_NAME = "docling-core"
DOCLING_READING_ORDER_CORE_PACKAGE_VERSION = "2.101.1"
DOCLING_READING_ORDER_RTREE_PACKAGE_NAME = "rtree"
DOCLING_READING_ORDER_RTREE_PACKAGE_VERSION = "1.4.1"
DOCLING_READING_ORDER_ALGORITHM = "reading_order_rb"


@dataclass(frozen=True, slots=True)
class DoclingReadingOrderConfiguration(AbstractActionConfiguration):
    """Pin package versions, algorithm identity, and element bound."""

    package_name: str = DOCLING_READING_ORDER_PACKAGE_NAME
    package_version: str = DOCLING_READING_ORDER_PACKAGE_VERSION
    core_package_name: str = DOCLING_READING_ORDER_CORE_PACKAGE_NAME
    core_package_version: str = DOCLING_READING_ORDER_CORE_PACKAGE_VERSION
    rtree_package_name: str = DOCLING_READING_ORDER_RTREE_PACKAGE_NAME
    rtree_package_version: str = DOCLING_READING_ORDER_RTREE_PACKAGE_VERSION
    algorithm_name: str = DOCLING_READING_ORDER_ALGORITHM
    maximum_elements: int = MAX_DOCLING_READING_ORDER_ELEMENTS
    configuration_id: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        values = (
            ("package_name", self.package_name),
            ("package_version", self.package_version),
            ("core_package_name", self.core_package_name),
            ("core_package_version", self.core_package_version),
            ("rtree_package_name", self.rtree_package_name),
            ("rtree_package_version", self.rtree_package_version),
            ("algorithm_name", self.algorithm_name),
        )
        normalized = tuple(
            LayoutValueValidation.require_text(name, value)
            for name, value in values
        )
        if normalized != (
            DOCLING_READING_ORDER_PACKAGE_NAME,
            DOCLING_READING_ORDER_PACKAGE_VERSION,
            DOCLING_READING_ORDER_CORE_PACKAGE_NAME,
            DOCLING_READING_ORDER_CORE_PACKAGE_VERSION,
            DOCLING_READING_ORDER_RTREE_PACKAGE_NAME,
            DOCLING_READING_ORDER_RTREE_PACKAGE_VERSION,
            DOCLING_READING_ORDER_ALGORITHM,
        ):
            raise ValueError("unsupported Docling reading-order implementation")
        maximum = LayoutValueValidation.require_positive_integer(
            "maximum_elements",
            self.maximum_elements,
            maximum=MAX_DOCLING_READING_ORDER_ELEMENTS,
        )
        object.__setattr__(self, "maximum_elements", maximum)
        object.__setattr__(
            self,
            "configuration_id",
            stable_id(
                "docling-reading-order-configuration",
                *normalized,
                maximum,
            ),
        )

    @property
    def provider_implementation_id(self) -> str:
        """Return the exact runtime implementation required by the request."""
        return (
            f"{self.package_name}:{self.package_version}/"
            f"{self.core_package_name}:{self.core_package_version}/"
            f"{self.rtree_package_name}:{self.rtree_package_version}/"
            f"{self.algorithm_name}"
        )
