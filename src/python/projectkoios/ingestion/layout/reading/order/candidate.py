"""Backend-neutral reading-order candidate evidence."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.proposal.kind import LayoutRegionKind
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation

from .kind import LayoutReadingDirection
from .limits import MAX_LAYOUT_READING_ORDER_ELEMENTS


@dataclass(frozen=True, slots=True, init=False)
class LayoutReadingOrderCandidate:
    """Own one bounded duplicate-free proposed region sequence."""

    _region_ids: tuple[str, ...] = field(repr=True)
    candidate_id: str = field(init=False)

    def __init__(self, *region_ids: str) -> None:
        if len(region_ids) > MAX_LAYOUT_READING_ORDER_ELEMENTS:
            raise ValueError(
                "reading-order candidate exceeds implementation limit"
            )
        values = tuple(
            LayoutValueValidation.require_text("region_id", region_id)
            for region_id in region_ids
        )
        if len(values) != len(set(values)):
            raise ValueError("candidate region IDs must be unique")
        object.__setattr__(self, "_region_ids", values)
        object.__setattr__(
            self,
            "candidate_id",
            stable_id("layout-reading-order-candidate", values),
        )

    def __iter__(self) -> Iterator[str]:
        return iter(self._region_ids)

    def __len__(self) -> int:
        return len(self._region_ids)


@dataclass(frozen=True, slots=True)
class LayoutReadingOrderCandidateElement(AbstractImmutableDataObject):
    """Retain one candidate producer element without vendor types."""

    region_id: str
    source_index: int
    kind: LayoutRegionKind
    bounding_box_pixels: tuple[float, float, float, float]
    element_id: str = field(init=False)

    def __post_init__(self) -> None:
        region = LayoutValueValidation.require_text("region_id", self.region_id)
        index = LayoutValueValidation.require_nonnegative_integer(
            "source_index",
            self.source_index,
            maximum=MAX_LAYOUT_READING_ORDER_ELEMENTS - 1,
        )
        if not isinstance(self.kind, LayoutRegionKind):
            raise TypeError("kind must be LayoutRegionKind")
        box = LayoutValueValidation.require_box(
            "bounding_box_pixels", self.bounding_box_pixels
        )
        object.__setattr__(self, "region_id", region)
        object.__setattr__(self, "source_index", index)
        object.__setattr__(self, "bounding_box_pixels", box)
        object.__setattr__(
            self,
            "element_id",
            stable_id(
                "layout-reading-order-candidate-element",
                region,
                index,
                self.kind,
                box,
            ),
        )


@dataclass(frozen=True, slots=True, init=False)
class LayoutReadingOrderCandidateElementInventory:
    """Own candidate elements in contiguous producer source order."""

    _elements: tuple[LayoutReadingOrderCandidateElement, ...] = field(repr=True)
    inventory_id: str = field(init=False)

    def __init__(self, *elements: LayoutReadingOrderCandidateElement) -> None:
        values = tuple(elements)
        if len(values) > MAX_LAYOUT_READING_ORDER_ELEMENTS:
            raise ValueError("candidate elements exceed implementation limit")
        if any(
            type(element) is not LayoutReadingOrderCandidateElement
            for element in values
        ):
            raise TypeError(
                "elements must be LayoutReadingOrderCandidateElement values"
            )
        indices = tuple(element.source_index for element in values)
        if indices != tuple(range(len(values))):
            raise ValueError("candidate source indexes must be contiguous")
        region_ids = tuple(element.region_id for element in values)
        if len(region_ids) != len(set(region_ids)):
            raise ValueError("candidate element region IDs must be unique")
        object.__setattr__(self, "_elements", values)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id(
                "layout-reading-order-candidate-element-inventory",
                tuple(element.element_id for element in values),
            ),
        )

    def __iter__(self) -> Iterator[LayoutReadingOrderCandidateElement]:
        return iter(self._elements)

    def __len__(self) -> int:
        return len(self._elements)


@dataclass(frozen=True, slots=True)
class LayoutReadingOrderCandidateEvidence(AbstractImmutableDataObject):
    """Bind candidate content to exact producer request and page evidence."""

    source_request_id: str
    producer_implementation_id: str
    render_id: str
    upstream_evidence_id: str
    direction: LayoutReadingDirection
    elements: LayoutReadingOrderCandidateElementInventory
    candidate: LayoutReadingOrderCandidate
    evidence_id: str = field(init=False)

    def __post_init__(self) -> None:
        source = LayoutValueValidation.require_text(
            "source_request_id", self.source_request_id
        )
        producer = LayoutValueValidation.require_text(
            "producer_implementation_id", self.producer_implementation_id
        )
        render = LayoutValueValidation.require_text("render_id", self.render_id)
        upstream = LayoutValueValidation.require_text(
            "upstream_evidence_id", self.upstream_evidence_id
        )
        if not isinstance(self.direction, LayoutReadingDirection):
            raise TypeError("direction must be LayoutReadingDirection")
        if (
            type(self.elements)
            is not LayoutReadingOrderCandidateElementInventory
        ):
            raise TypeError(
                "elements must be LayoutReadingOrderCandidateElementInventory"
            )
        if type(self.candidate) is not LayoutReadingOrderCandidate:
            raise TypeError("candidate must be LayoutReadingOrderCandidate")
        object.__setattr__(self, "source_request_id", source)
        object.__setattr__(self, "producer_implementation_id", producer)
        object.__setattr__(self, "render_id", render)
        object.__setattr__(self, "upstream_evidence_id", upstream)
        object.__setattr__(
            self,
            "evidence_id",
            stable_id(
                "layout-reading-order-candidate-evidence",
                source,
                producer,
                render,
                upstream,
                self.direction,
                self.elements.inventory_id,
                self.candidate.candidate_id,
            ),
        )
