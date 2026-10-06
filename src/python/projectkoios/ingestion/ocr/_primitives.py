"""Private primitive bounds and value validation for OCR evidence."""

from __future__ import annotations

import math
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import TYPE_CHECKING

from projectkoios.ingestion.models import (
    BoundingBox,
    Metadata,
)
from projectkoios.ingestion.ocr._limits import (
    _GRANDFATHERED_LANGUAGE_TAGS,
    _MAX_IDENTITY_FIELD_CHARACTERS,
    _MAX_LANGUAGE_CHARACTERS,
    _MAX_WARNING_EVIDENCE_CHARACTERS,
    _MAX_WARNING_EVIDENCE_ENTRIES,
    _MAX_WARNING_MESSAGE_CHARACTERS,
)
from projectkoios.ingestion.ocr.limit_error import OCRContractLimitError
from projectkoios.ingestion.pdf.models import (
    RenderedRegion,
)
from projectkoios.ingestion.sha256.hash import SHA256Hash

if TYPE_CHECKING:
    from projectkoios.ingestion.ocr.confidence import OCRConfidence


def _finite_box(box: BoundingBox, name: str) -> BoundingBox:
    if not isinstance(box, tuple):
        raise TypeError(f"{name} must be an immutable tuple")
    if len(box) != 4:
        raise ValueError(f"{name} must contain four coordinates")
    values: list[float] = []
    for coordinate in box:
        if isinstance(coordinate, bool) or not isinstance(
            coordinate, int | float
        ):
            raise ValueError(f"{name} coordinates must be finite numbers")
        try:
            value = float(coordinate)
        except OverflowError as error:
            raise ValueError(
                f"{name} coordinates must be finite numbers"
            ) from error
        if not math.isfinite(value):
            raise ValueError(f"{name} coordinates must be finite numbers")
        values.append(0.0 if value == 0.0 else value)
    x0, y0, x1, y1 = values
    if x1 <= x0 or y1 <= y0:
        raise ValueError(f"{name} must have positive area")
    return (x0, y0, x1, y1)


def _confidence_value(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("OCR confidence must be a finite number")
    try:
        normalized = float(value)
    except OverflowError as error:
        raise ValueError("OCR confidence must be a finite number") from error
    if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
        raise ValueError("OCR confidence must be between zero and one")
    return 0.0 if normalized == 0.0 else normalized


def _validate_confidence(value: OCRConfidence | None) -> None:
    from projectkoios.ingestion.ocr.confidence import OCRConfidence

    if value is not None and not isinstance(value, OCRConfidence):
        raise TypeError("confidence must be OCRConfidence or None")


def _box_contains(outer: BoundingBox, inner: BoundingBox) -> bool:
    return (
        outer[0] <= inner[0]
        and outer[1] <= inner[1]
        and outer[2] >= inner[2]
        and outer[3] >= inner[3]
    )


def _same_processor_identity(first: object, second: object) -> None:
    identity_fields = (
        "processor_name",
        "processor_version",
        "backend_name",
        "backend_version",
    )
    if any(
        getattr(first, name) != getattr(second, name)
        for name in identity_fields
    ):
        raise ValueError("OCR processor/backend identity is contradictory")


def _validate_contract_size(value: object, limit: int) -> None:
    """Bound retained evidence without materializing canonical JSON."""

    total = 0
    stack: list[object] = [value]
    while stack:
        item = stack.pop()
        if item is None:
            increment = 4
        elif isinstance(item, str):
            increment = len(item.encode("utf-8")) + 2
        elif isinstance(item, bytes):
            increment = len(item)
        elif isinstance(item, Enum):
            stack.append(item.value)
            increment = 0
        elif isinstance(item, bool | int | float):
            increment = 32
        elif isinstance(item, tuple):
            increment = 2 + len(item)
            stack.extend(item)
        elif is_dataclass(item) and not isinstance(item, type):
            increment = 2
            for field in fields(item):
                increment += len(field.name) + 3
                if isinstance(item, RenderedRegion) and field.name == "content":
                    # Input PNG bytes have separate OCRConfiguration bounds.
                    continue
                stack.append(getattr(item, field.name))
        else:
            raise TypeError("OCR result contains unsupported contract evidence")
        total += increment
        if total > limit:
            raise OCRContractLimitError("OCR result exceeds max_result_bytes")


def _canonical_language_tag(value: object) -> str:
    _hard_bounded_string(
        "language",
        value,
        nonempty=True,
        limit=_MAX_LANGUAGE_CHARACTERS,
    )
    assert isinstance(value, str)
    lowered = value.casefold()
    if lowered in _GRANDFATHERED_LANGUAGE_TAGS:
        return lowered
    if "_" in value or value.startswith("-") or value.endswith("-"):
        raise ValueError("language must be a well-formed BCP 47 tag")
    subtags = value.split("-")
    if any(
        not 1 <= len(subtag) <= 8
        or not subtag.isascii()
        or not subtag.isalnum()
        for subtag in subtags
    ):
        raise ValueError("language must be a well-formed BCP 47 tag")
    if subtags[0].casefold() == "x":
        if len(subtags) < 2:
            raise ValueError("language must be a well-formed BCP 47 tag")
        return "-".join(subtag.lower() for subtag in subtags)

    primary = subtags[0]
    if not primary.isalpha() or not 2 <= len(primary) <= 8:
        raise ValueError("language must be a well-formed BCP 47 tag")
    canonical = [primary.lower()]
    index = 1
    if len(primary) in (2, 3):
        extlang_count = 0
        while (
            index < len(subtags)
            and extlang_count < 3
            and len(subtags[index]) == 3
            and subtags[index].isalpha()
        ):
            canonical.append(subtags[index].lower())
            index += 1
            extlang_count += 1
    if (
        index < len(subtags)
        and len(subtags[index]) == 4
        and subtags[index].isalpha()
    ):
        canonical.append(subtags[index].title())
        index += 1
    if index < len(subtags) and (
        len(subtags[index]) == 2
        and subtags[index].isalpha()
        or len(subtags[index]) == 3
        and subtags[index].isdigit()
    ):
        canonical.append(subtags[index].upper())
        index += 1

    variants: set[str] = set()
    while index < len(subtags) and (
        5 <= len(subtags[index]) <= 8
        or len(subtags[index]) == 4
        and subtags[index][0].isdigit()
    ):
        variant = subtags[index].lower()
        if variant in variants:
            raise ValueError("language variants must be unique")
        variants.add(variant)
        canonical.append(variant)
        index += 1

    extensions: set[str] = set()
    while (
        index < len(subtags)
        and len(subtags[index]) == 1
        and subtags[index].casefold() != "x"
    ):
        singleton = subtags[index].lower()
        if singleton in extensions:
            raise ValueError("language extensions must be unique")
        extensions.add(singleton)
        canonical.append(singleton)
        index += 1
        start = index
        while index < len(subtags) and 2 <= len(subtags[index]) <= 8:
            canonical.append(subtags[index].lower())
            index += 1
        if index == start:
            raise ValueError("language extension has no value")

    if index < len(subtags) and subtags[index].casefold() == "x":
        canonical.append("x")
        index += 1
        if index == len(subtags):
            raise ValueError("language private use has no value")
        canonical.extend(subtag.lower() for subtag in subtags[index:])
        index = len(subtags)
    if index != len(subtags):
        raise ValueError("language must be a well-formed BCP 47 tag")
    return "-".join(canonical)


def _validate_sha256(name: str, value: object) -> None:
    if not SHA256Hash.is_canonical(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


def _hard_bounded_string(
    name: str,
    value: object,
    *,
    nonempty: bool = False,
    limit: int = _MAX_IDENTITY_FIELD_CHARACTERS,
) -> None:

    if not isinstance(value, str) or (nonempty and not value):
        qualifier = "non-empty " if nonempty else ""
        raise ValueError(f"{name} must be a {qualifier}string")
    if len(value) > limit:
        raise OCRContractLimitError(
            f"{name} exceeds the implementation maximum ({limit})"
        )
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(f"{name} must be valid UTF-8") from error


def _validate_metadata(metadata: Metadata) -> None:

    _require_tuple("evidence", metadata)
    if len(metadata) > _MAX_WARNING_EVIDENCE_ENTRIES:
        raise OCRContractLimitError(
            "warning evidence exceeds the implementation maximum"
        )
    total_characters = 0
    for entry in metadata:
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise TypeError("warning evidence entries must be immutable pairs")
        _hard_bounded_string("warning evidence key", entry[0], nonempty=True)
        _hard_bounded_string(
            "warning evidence value",
            entry[1],
            limit=_MAX_WARNING_MESSAGE_CHARACTERS,
        )
        total_characters += len(entry[0]) + len(entry[1])
        if total_characters > _MAX_WARNING_EVIDENCE_CHARACTERS:
            raise OCRContractLimitError(
                "warning evidence exceeds the character safety limit"
            )
    if len({key for key, _ in metadata}) != len(metadata):
        raise ValueError("warning evidence keys must be unique")


def _require_identity_fields(*values: str) -> None:
    for value in values:
        _hard_bounded_string("OCR identity field", value, nonempty=True)


def _require_unique_strings(
    name: str,
    values: tuple[str, ...],
    *,
    required: bool = False,
    string_limit: int = _MAX_IDENTITY_FIELD_CHARACTERS,
) -> None:
    _require_tuple(name, values)
    if required and not values:
        raise ValueError(f"{name} must be non-empty")
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must be unique")
    for value in values:
        _hard_bounded_string(name, value, nonempty=True, limit=string_limit)


def _bounded_string(
    name: str, value: str, limit: int, *, nonempty: bool = False
) -> None:

    if not isinstance(value, str) or (nonempty and not value):
        qualifier = "non-empty " if nonempty else ""
        raise ValueError(f"{name} must be a {qualifier}string")
    if len(value) > limit:
        raise OCRContractLimitError(f"{name} exceeds its configured limit")
    _valid_utf8_string(name, value, nonempty=nonempty)


def _valid_utf8_string(
    name: str, value: object, *, nonempty: bool = False
) -> None:
    if not isinstance(value, str) or (nonempty and not value):
        qualifier = "non-empty " if nonempty else ""
        raise ValueError(f"{name} must be a {qualifier}string")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(f"{name} must be valid UTF-8") from error


def _positive_integer(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _nonnegative_integer(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _optional_nonnegative_integer(name: str, value: object) -> None:
    if value is not None:
        _nonnegative_integer(name, value)


def _require_tuple(name: str, value: object) -> None:
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be an immutable tuple")
