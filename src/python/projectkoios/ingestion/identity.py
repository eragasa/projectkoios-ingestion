from __future__ import annotations

import hashlib
import json
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any


def to_json_value(value: object) -> Any:
    """Convert a contract value into JSON-compatible built-in values."""
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: to_json_value(getattr(value, field.name))
            for field in fields(value)
        }

    if isinstance(value, Enum):
        return to_json_value(value.value)

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, bytes):
        return {"hex": value.hex()}

    if isinstance(value, dict):
        return {str(key): to_json_value(item) for key, item in value.items()}

    if isinstance(value, (list, tuple)):
        return [to_json_value(item) for item in value]

    if value is None or isinstance(value, str | int | float | bool):
        return value

    raise TypeError(f"Value is not JSON serializable: {type(value).__name__}")


def canonical_json(value: object) -> str:
    """Serialize a contract value deterministically."""
    return json.dumps(
        to_json_value(value),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def sha256_digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def stable_id(namespace: str, *identity_parts: object) -> str:
    if not namespace or ":" in namespace:
        raise ValueError("namespace must be non-empty and cannot contain ':'")

    digest = sha256_digest(canonical_json(identity_parts).encode("utf-8"))
    return f"{namespace}:sha256:{digest}"
