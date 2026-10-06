"""Figure-relevance value validation."""

from __future__ import annotations

import math
from dataclasses import fields, is_dataclass
from enum import Enum

from projectkoios.ingestion.figures.relevance.limits.definition import (
    _MAX_EVIDENCE_CHARACTERS,
    _MAX_EVIDENCE_ENTRIES,
    _MAX_IDENTITY_CHARACTERS,
)
from projectkoios.ingestion.figures.relevance.limits.error import (
    FigureRelevanceLimitError,
)
from projectkoios.ingestion.figures.relevance.validation import (
    value as value_validation,
)
from projectkoios.ingestion.models import Metadata
from projectkoios.ingestion.sha256.hash import SHA256Hash


def _validate_metadata(value: Metadata) -> None:
    value_validation._require_tuple("metadata", value)
    if len(value) > _MAX_EVIDENCE_ENTRIES:
        raise FigureRelevanceLimitError("too many metadata entries")
    total = 0
    for entry in value:
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise TypeError("metadata must contain immutable pairs")
        key, item = entry
        value_validation._bounded_string("metadata key", key, nonempty=True)
        value_validation._bounded_string("metadata value", item)
        total += len(key) + len(item)
    if total > _MAX_EVIDENCE_CHARACTERS:
        raise FigureRelevanceLimitError("metadata exceeds its hard limit")


def _identity_fields(*values: str) -> None:
    for value in values:
        value_validation._bounded_string("identity field", value, nonempty=True)


def _unique_strings(name: str, values: tuple[str, ...]) -> None:
    value_validation._require_tuple(name, values)
    for value in values:
        value_validation._bounded_string(name, value, nonempty=True)
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must be unique")


def _require_tuple(name: str, value: object) -> None:
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be an immutable tuple")


def _bounded_string(
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
        raise FigureRelevanceLimitError(f"{name} exceeds its hard limit")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(f"{name} must be valid UTF-8") from error


def _positive_integer(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _finite_float(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return 0.0 if result == 0.0 else result


def _unit_float(name: str, value: object) -> float:
    result = value_validation._finite_float(name, value)
    if not 0.0 <= result <= 1.0:
        raise ValueError(f"{name} must be within [0, 1]")
    return result


def _sha256(name: str, value: str) -> None:
    if not SHA256Hash.is_canonical(value):
        raise ValueError(f"{name} must be a SHA-256 digest")


def _validate_retained_size(value: object, limit: int) -> None:
    total = 0
    stack = [value]
    seen: set[int] = set()
    while stack:
        item = stack.pop()
        if item is None or isinstance(item, (bool, int, float, Enum)):
            total += 16
        elif isinstance(item, str):
            total += len(item.encode("utf-8")) + 8
        elif isinstance(item, bytes):
            total += len(item)
        elif isinstance(item, tuple):
            marker = id(item)
            if marker in seen:
                continue
            seen.add(marker)
            total += 8 * len(item)
            stack.extend(item)
        elif is_dataclass(item) and not isinstance(item, type):
            marker = id(item)
            if marker in seen:
                continue
            seen.add(marker)
            for field in fields(item):
                total += len(field.name) + 3
                if field.name in (
                    "content",
                    "mask_content",
                ) and item.__class__.__name__ in (
                    "RenderedRegion",
                    "EmbeddedFigureArtifact",
                ):
                    continue
                stack.append(getattr(item, field.name))
        else:
            raise TypeError(
                "figure-relevance result contains unsupported evidence"
            )
        if total > limit:
            raise FigureRelevanceLimitError(
                "figure-relevance result exceeds max_result_bytes"
            )
