"""Bounded value validation for accepted table evidence."""

from __future__ import annotations

import math
import re
from datetime import datetime

_SHA256 = re.compile(r"[0-9a-f]{64}")
_DECIMAL = re.compile(r"-?\d+\.\d{4}")
_UTC_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z")
_MAX_TEXT = 65_536
_MAX_IDENTITY = 4_096
_MAX_ROWS = 512
_MAX_COLUMNS = 128


def require_text(name: str, value: object, *, identity: bool = False) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be non-empty text")
    limit = _MAX_IDENTITY if identity else _MAX_TEXT
    if len(value) > limit:
        raise ValueError(f"{name} exceeds its character limit")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(f"{name} must be valid UTF-8") from error
    return value


def require_sha256(name: str, value: object) -> str:
    text = require_text(name, value, identity=True)
    if _SHA256.fullmatch(text) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return text


def require_id(name: str, value: object, prefix: str) -> str:
    text = require_text(name, value, identity=True)
    if not text.startswith(f"{prefix}:sha256:"):
        raise ValueError(f"{name} has an unsupported identity namespace")
    require_sha256(name, text.removeprefix(f"{prefix}:sha256:"))
    return text


def require_index(name: str, value: object, *, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    if value >= maximum:
        raise ValueError(f"{name} exceeds its implementation limit")
    return value


def require_positive(name: str, value: object, *, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    if value > maximum:
        raise ValueError(f"{name} exceeds its implementation limit")
    return value


def require_row_index(name: str, value: object) -> int:
    return require_index(name, value, maximum=_MAX_ROWS)


def require_column_index(name: str, value: object) -> int:
    return require_index(name, value, maximum=_MAX_COLUMNS)


def require_decimal_text(name: str, value: object) -> str:
    text = require_text(name, value, identity=True)
    if _DECIMAL.fullmatch(text) is None:
        raise ValueError(f"{name} must preserve sign and four decimal places")
    return text


def require_string_tuple(
    name: str,
    value: object,
    *,
    unique: bool = False,
    required: bool = False,
) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be an immutable tuple")
    if required and not value:
        raise ValueError(f"{name} must be non-empty")
    for item in value:
        require_text(name, item, identity=True)
    if unique and len(set(value)) != len(value):
        raise ValueError(f"{name} must be unique")
    return value


def require_box(name: str, value: object) -> tuple[float, float, float, float]:
    if not isinstance(value, tuple) or len(value) != 4:
        raise TypeError(f"{name} must be an immutable four-value tuple")
    normalized: list[float] = []
    for coordinate in value:
        if isinstance(coordinate, bool) or not isinstance(
            coordinate, int | float
        ):
            raise TypeError(f"{name} coordinates must be numeric")
        item = float(coordinate)
        if not math.isfinite(item):
            raise ValueError(f"{name} coordinates must be finite")
        normalized.append(0.0 if item == 0.0 else item)
    box = (normalized[0], normalized[1], normalized[2], normalized[3])
    if box[2] <= box[0] or box[3] <= box[1]:
        raise ValueError(f"{name} must have positive area")
    return box


def parse_utc_timestamp(name: str, value: object) -> datetime:
    text = require_text(name, value, identity=True)
    if _UTC_TIMESTAMP.fullmatch(text) is None:
        raise ValueError(f"{name} must be an ISO-8601 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(text.removesuffix("Z") + "+00:00")
    except ValueError as error:
        raise ValueError(f"{name} must be an ISO-8601 UTC timestamp") from error
    offset = parsed.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise ValueError(f"{name} must be UTC")
    return parsed
