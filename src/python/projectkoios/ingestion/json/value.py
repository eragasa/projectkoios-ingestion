"""Closed JSON values and immutable-object projection."""

from __future__ import annotations

import math
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from pathlib import PurePath
from typing import cast

from projectkoios.ingestion.json.error import JsonSerializationError
from projectkoios.ingestion.json.limits.definition import JsonLimits
from projectkoios.ingestion.json.limits.error import JsonLimitError

type JsonValue = (
    None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
)


@dataclass(slots=True)
class _ProjectionState:
    item_count: int = 0
    total_string_bytes: int = 0


@dataclass(frozen=True, slots=True)
class JsonValueProjector:
    """Project supported immutable values into a bounded JSON tree."""

    limits: JsonLimits
    allow_non_finite: bool = False

    def __post_init__(self) -> None:
        if type(self.allow_non_finite) is not bool:
            raise TypeError("allow_non_finite must be a boolean")

    def project(self, value: object) -> JsonValue:
        state = _ProjectionState()
        return self._project(
            value,
            container_depth=0,
            active_ids=set(),
            state=state,
        )

    def project_object(self, value: object) -> dict[str, JsonValue]:
        projected = self.project(value)
        if not isinstance(projected, dict):
            raise JsonSerializationError("JSON root must be an object")
        return projected

    def _project(
        self,
        value: object,
        *,
        container_depth: int,
        active_ids: set[int],
        state: _ProjectionState,
    ) -> JsonValue:
        self._consume_item(state)
        if isinstance(value, Enum):
            value = value.value
        if value is None or type(value) is bool:
            return cast(None | bool, value)
        if type(value) is int:
            self._require_number_characters(str(abs(cast(int, value))))
            return cast(int, value)
        if type(value) is float:
            number = cast(float, value)
            if not math.isfinite(number) and not self.allow_non_finite:
                raise JsonSerializationError("JSON float must be finite")
            self._require_number_characters(repr(number))
            return number
        if isinstance(value, str):
            string = str(value)
            self._consume_string(string, state)
            return string
        if isinstance(value, PurePath):
            path = str(value)
            self._consume_string(path, state)
            return path
        if isinstance(value, bytes):
            return self._project_container(
                {"hex": value.hex()},
                container_depth=container_depth,
                active_ids=active_ids,
                state=state,
                already_counted=True,
            )
        if is_dataclass(value) and not isinstance(value, type):
            return self._project_container(
                {
                    field.name: getattr(value, field.name)
                    for field in fields(value)
                },
                container_depth=container_depth,
                active_ids=active_ids,
                state=state,
                source=value,
                already_counted=True,
            )
        if isinstance(value, dict | list | tuple):
            return self._project_container(
                value,
                container_depth=container_depth,
                active_ids=active_ids,
                state=state,
                already_counted=True,
            )
        raise JsonSerializationError(
            f"value is not JSON serializable: {type(value).__name__}"
        )

    def _project_container(
        self,
        value: object,
        *,
        container_depth: int,
        active_ids: set[int],
        state: _ProjectionState,
        already_counted: bool,
        source: object | None = None,
    ) -> JsonValue:
        if not already_counted:
            self._consume_item(state)
        next_depth = container_depth + 1
        if next_depth > self.limits.maximum_container_depth:
            raise JsonLimitError("JSON container depth exceeds its limit")
        cycle_value = source if source is not None else value
        identity = id(cycle_value)
        if identity in active_ids:
            raise JsonSerializationError("JSON value contains a cycle")
        active_ids.add(identity)
        try:
            if isinstance(value, dict):
                result: dict[str, JsonValue] = {}
                for key, child in value.items():
                    if not isinstance(key, str):
                        raise JsonSerializationError(
                            "JSON object keys must be strings"
                        )
                    string_key = str(key)
                    self._consume_item(state)
                    self._consume_string(string_key, state)
                    if string_key in result:
                        raise JsonSerializationError(
                            "JSON object contains a duplicate key"
                        )
                    result[string_key] = self._project(
                        child,
                        container_depth=next_depth,
                        active_ids=active_ids,
                        state=state,
                    )
                return result
            if isinstance(value, list | tuple):
                return [
                    self._project(
                        child,
                        container_depth=next_depth,
                        active_ids=active_ids,
                        state=state,
                    )
                    for child in value
                ]
        finally:
            active_ids.remove(identity)
        raise JsonSerializationError("unsupported JSON container")

    def _consume_item(self, state: _ProjectionState) -> None:
        state.item_count += 1
        if state.item_count > self.limits.maximum_items:
            raise JsonLimitError("JSON item count exceeds its limit")

    def _consume_string(self, value: str, state: _ProjectionState) -> None:
        try:
            byte_length = len(value.encode("utf-8", errors="strict"))
        except UnicodeError as error:
            raise JsonSerializationError(
                "JSON string is not valid UTF-8"
            ) from error
        if byte_length > self.limits.maximum_string_bytes:
            raise JsonLimitError("JSON string exceeds its byte limit")
        state.total_string_bytes += byte_length
        if state.total_string_bytes > self.limits.maximum_total_string_bytes:
            raise JsonLimitError("JSON strings exceed their aggregate limit")

    def _require_number_characters(self, value: str) -> None:
        if len(value) > self.limits.maximum_number_characters:
            raise JsonLimitError("JSON number exceeds its character limit")
