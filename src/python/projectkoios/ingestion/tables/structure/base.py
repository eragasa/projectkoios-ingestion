"""Shared immutable base for table-structure data objects."""

from __future__ import annotations

import math
from abc import ABC

from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.models import BoundingBox, Metadata, SourceSpan
from projectkoios.ingestion.tables.structure.bounds import (
    _MAX_IDENTITY_CHARACTERS,
    _MAX_METADATA_CHARACTERS,
    _MAX_SOURCE_SPANS,
    _MAX_TEXT_CHARACTERS,
)
from projectkoios.ingestion.tables.structure.limit_error import (
    TableStructureLimitError,
)


class AbstractTableStructureDataObject(AbstractImmutableDataObject, ABC):
    """Own shared bounded-value invariants for table-structure objects."""

    __slots__ = ()

    @classmethod
    def _validate_identity_fields(cls, *values: str) -> None:
        for value in values:
            cls._validate_bounded_string("identity field", value, nonempty=True)

    @classmethod
    def _validate_unique_strings(
        cls,
        name: str,
        values: tuple[str, ...],
        *,
        required: bool = False,
    ) -> None:
        if not isinstance(values, tuple):
            raise TypeError(f"{name} must be an immutable tuple")
        if required and not values:
            raise ValueError(f"{name} must be non-empty")
        for value in values:
            cls._validate_bounded_string(name, value, nonempty=True)
        if len(set(values)) != len(values):
            raise ValueError(f"{name} must be unique")

    @staticmethod
    def _validate_spans(spans: tuple[SourceSpan, ...]) -> None:
        if not isinstance(spans, tuple) or not spans:
            raise ValueError("source spans must be a non-empty immutable tuple")
        if len(spans) > _MAX_SOURCE_SPANS:
            raise TableStructureLimitError(
                "source spans exceed their hard limit"
            )
        if any(not isinstance(span, SourceSpan) for span in spans):
            raise TypeError("source spans contain an unsupported value")

    @classmethod
    def _validate_metadata(cls, value: Metadata) -> None:
        if not isinstance(value, tuple):
            raise TypeError("metadata must be an immutable tuple")
        total = 0
        for entry in value:
            if not isinstance(entry, tuple) or len(entry) != 2:
                raise TypeError("metadata must contain immutable pairs")
            key, item = entry
            cls._validate_bounded_string("metadata key", key, nonempty=True)
            cls._validate_bounded_string("metadata value", item)
            total += len(key) + len(item)
            if total > _MAX_METADATA_CHARACTERS:
                raise TableStructureLimitError(
                    "metadata exceeds its hard limit"
                )

    @staticmethod
    def _validate_bounded_string(
        name: str,
        value: object,
        *,
        nonempty: bool = False,
        limit: int = _MAX_IDENTITY_CHARACTERS,
    ) -> None:
        if not isinstance(value, str):
            raise TypeError(f"{name} must be a string")
        if nonempty and not value:
            raise ValueError(f"{name} must be non-empty")
        if len(value) > limit:
            raise TableStructureLimitError(f"{name} exceeds its hard limit")
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as error:
            raise ValueError(f"{name} must be valid UTF-8") from error

    @classmethod
    def _validate_bounded_text(cls, name: str, value: object) -> None:
        cls._validate_bounded_string(name, value, limit=_MAX_TEXT_CHARACTERS)

    @staticmethod
    def _validate_positive_integer(name: str, value: object) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")

    @staticmethod
    def _validate_nonnegative_integer(name: str, value: object) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")

    @staticmethod
    def _validate_finite_float(name: str, value: object) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be numeric")
        result = float(value)
        if not math.isfinite(result):
            raise ValueError(f"{name} must be finite")
        return result

    @classmethod
    def _validate_unit_float(cls, name: str, value: object) -> float:
        result = cls._validate_finite_float(name, value)
        if not 0.0 <= result <= 1.0:
            raise ValueError(f"{name} must be within [0, 1]")
        return result

    @classmethod
    def _validate_box(cls, value: object) -> BoundingBox:
        if not isinstance(value, tuple) or len(value) != 4:
            raise TypeError(
                "bounding box must be an immutable four-value tuple"
            )
        x0, y0, x1, y1 = (
            cls._validate_finite_float("bounding-box coordinate", item)
            for item in value
        )
        if x1 <= x0 or y1 <= y0:
            raise ValueError("bounding box must have positive area")
        return (x0, y0, x1, y1)
