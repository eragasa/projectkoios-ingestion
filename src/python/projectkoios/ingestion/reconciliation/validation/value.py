"""Private primitive bounds and value validation for reconciliation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from projectkoios.ingestion.models import (
    Metadata,
)
from projectkoios.ingestion.reconciliation.limit.definition import (
    _MAX_IDENTITY_CHARACTERS,
    _MAX_LINKED_IDS,
    _MAX_TEXT_CHARACTERS_PER_ITEM,
    _MAX_WARNING_EVIDENCE_CHARACTERS,
    _MAX_WARNING_EVIDENCE_ENTRIES,
)
from projectkoios.ingestion.reconciliation.limit.error import (
    OCRReconciliationLimitError,
)

if TYPE_CHECKING:
    pass


def _validate_metadata(value: Metadata) -> None:

    _require_tuple("warning evidence", value)
    if len(value) > _MAX_WARNING_EVIDENCE_ENTRIES:
        raise OCRReconciliationLimitError(
            "warning evidence exceeds the entry limit"
        )
    total_characters = 0
    for entry in value:
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise TypeError("warning evidence must contain immutable pairs")
        _bounded_string("warning evidence key", entry[0])
        _bounded_text("warning evidence value", entry[1])
        total_characters += len(entry[0]) + len(entry[1])
        if total_characters > _MAX_WARNING_EVIDENCE_CHARACTERS:
            raise OCRReconciliationLimitError(
                "warning evidence exceeds the character limit"
            )


def _require_unique_strings(
    name: str, values: tuple[str, ...], required: bool = False
) -> None:

    _require_tuple(name, values)
    if len(values) > _MAX_LINKED_IDS:
        raise OCRReconciliationLimitError(f"{name} exceeds the linked-ID limit")
    if required and not values:
        raise ValueError(f"{name} must be non-empty")
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must be unique")
    for value in values:
        _bounded_string(name, value)


def _require_tuple(name: str, value: object) -> None:
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be an immutable tuple")


def _bounded_string(name: str, value: object) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value or len(value) > _MAX_IDENTITY_CHARACTERS:
        raise ValueError(
            f"{name} must contain 1 to {_MAX_IDENTITY_CHARACTERS} characters"
        )
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise ValueError(f"{name} must be valid UTF-8") from error


def _bounded_text(
    name: str,
    value: object,
    *,
    nonempty: bool = False,
    limit: int = _MAX_TEXT_CHARACTERS_PER_ITEM,
) -> None:

    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if nonempty and not value:
        raise ValueError(f"{name} must be non-empty")
    if len(value) > limit:
        raise OCRReconciliationLimitError(f"{name} exceeds its limit")
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise ValueError(f"{name} must be valid UTF-8") from error


def _positive_integer(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _nonnegative_integer(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
