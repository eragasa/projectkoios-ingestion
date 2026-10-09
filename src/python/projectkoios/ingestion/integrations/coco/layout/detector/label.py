"""Explicit detector-label disposition and profile mapping evidence."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation


class CocoLayoutDetectorLabelDisposition(StrEnum):
    """State whether one model label enters profile-v0.1 annotations."""

    ACCEPTED = "accepted"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class CocoLayoutDetectorLabelMapping(AbstractImmutableDataObject):
    """Map one exact model label ID or retain its unsupported status."""

    model_label_id: int
    model_label: str
    disposition: CocoLayoutDetectorLabelDisposition
    category_id: int | None
    mapping_id: str = field(init=False)

    def __post_init__(self) -> None:
        label_id = LayoutValueValidation.require_nonnegative_integer(
            "model_label_id", self.model_label_id
        )
        label = LayoutValueValidation.require_text(
            "model_label", self.model_label
        )
        if not isinstance(self.disposition, CocoLayoutDetectorLabelDisposition):
            raise TypeError(
                "disposition must be CocoLayoutDetectorLabelDisposition"
            )
        category_id = self.category_id
        if self.disposition is CocoLayoutDetectorLabelDisposition.ACCEPTED:
            category_id = LayoutValueValidation.require_positive_integer(
                "category_id", category_id
            )
        elif category_id is not None:
            raise ValueError(
                "unsupported detector labels cannot identify a category"
            )
        object.__setattr__(self, "model_label_id", label_id)
        object.__setattr__(self, "model_label", label)
        object.__setattr__(self, "category_id", category_id)
        object.__setattr__(
            self,
            "mapping_id",
            stable_id(
                "coco-layout-detector-label-mapping",
                label_id,
                label,
                self.disposition,
                category_id,
            ),
        )


@dataclass(frozen=True, slots=True, init=False)
class CocoLayoutDetectorLabelMappingInventory:
    """Own one ordered, unique, bounded detector-label registry."""

    _mappings: tuple[CocoLayoutDetectorLabelMapping, ...] = field(repr=True)
    inventory_id: str = field(init=False)

    def __init__(self, *mappings: CocoLayoutDetectorLabelMapping) -> None:
        values = tuple(mappings)
        if not values:
            raise ValueError("detector label mapping inventory cannot be empty")
        if len(values) > 64:
            raise ValueError("detector label mapping count exceeds 64")
        if any(
            type(value) is not CocoLayoutDetectorLabelMapping
            for value in values
        ):
            raise TypeError(
                "detector label mapping inventory requires exact mappings"
            )
        label_ids = tuple(value.model_label_id for value in values)
        labels = tuple(value.model_label for value in values)
        if label_ids != tuple(range(len(values))):
            raise ValueError(
                "detector model label IDs must be contiguous from zero"
            )
        if len(labels) != len(set(labels)):
            raise ValueError("detector model labels must be unique")
        accepted_categories = tuple(
            value.category_id
            for value in values
            if value.disposition is CocoLayoutDetectorLabelDisposition.ACCEPTED
        )
        if len(accepted_categories) != len(set(accepted_categories)):
            raise ValueError(
                "accepted detector labels must map to unique categories"
            )
        object.__setattr__(self, "_mappings", values)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id(
                "coco-layout-detector-label-mapping-inventory",
                tuple(value.mapping_id for value in values),
            ),
        )

    def __iter__(self) -> Iterator[CocoLayoutDetectorLabelMapping]:
        return iter(self._mappings)

    def __len__(self) -> int:
        return len(self._mappings)

    def require(self, model_label_id: int) -> CocoLayoutDetectorLabelMapping:
        """Return one exact model-label mapping or fail closed."""
        if (
            isinstance(model_label_id, bool)
            or not isinstance(model_label_id, int)
            or not 0 <= model_label_id < len(self._mappings)
        ):
            raise ValueError("detector model label ID is absent")
        mapping = self._mappings[model_label_id]
        if mapping.model_label_id != model_label_id:
            raise ValueError("detector model label registry is inconsistent")
        return mapping

    @classmethod
    def docling_heron_v0_1(cls) -> CocoLayoutDetectorLabelMappingInventory:
        """Map Heron's DocLayNet-compatible labels and retain extensions."""
        # Heron IDs 0-10 align with the DocLayNet vocabulary; Koios COCO
        # category IDs are one-indexed, so the accepted mapping is ``id + 1``.
        labels = (
            "caption",
            "footnote",
            "formula",
            "list_item",
            "page_footer",
            "page_header",
            "picture",
            "section_header",
            "table",
            "text",
            "title",
            "document_index",
            "code",
            "checkbox_selected",
            "checkbox_unselected",
            "form",
            "key_value_region",
        )
        # Retain Heron's six extension labels as explicit unsupported evidence
        # instead of dropping them or coercing them into a profile category.
        return cls(
            *(
                CocoLayoutDetectorLabelMapping(
                    model_label_id=index,
                    model_label=label,
                    disposition=(
                        CocoLayoutDetectorLabelDisposition.ACCEPTED
                        if index < 11
                        else CocoLayoutDetectorLabelDisposition.UNSUPPORTED
                    ),
                    category_id=index + 1 if index < 11 else None,
                )
                for index, label in enumerate(labels)
            )
        )
