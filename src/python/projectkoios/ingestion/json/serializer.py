"""Deterministic bounded JSON formatting."""

from __future__ import annotations

import json
from dataclasses import dataclass

from projectkoios.ingestion.json.error import JsonSerializationError
from projectkoios.ingestion.json.limits.definition import JsonLimits
from projectkoios.ingestion.json.limits.error import JsonLimitError
from projectkoios.ingestion.json.value import JsonValue, JsonValueProjector


@dataclass(frozen=True, slots=True)
class JsonSerializer:
    """Serialize closed JSON values with explicit byte-affecting options."""

    limits: JsonLimits
    ensure_ascii: bool
    sort_keys: bool
    allow_non_finite: bool
    indent: int | None
    separators: tuple[str, str] | None
    terminal_newline: bool

    def __post_init__(self) -> None:
        if type(self.ensure_ascii) is not bool:
            raise TypeError("ensure_ascii must be a boolean")
        if type(self.sort_keys) is not bool:
            raise TypeError("sort_keys must be a boolean")
        if type(self.allow_non_finite) is not bool:
            raise TypeError("allow_non_finite must be a boolean")
        if self.indent is not None and (
            isinstance(self.indent, bool)
            or not isinstance(self.indent, int)
            or self.indent < 0
        ):
            raise ValueError("indent must be null or a non-negative integer")
        if self.separators is not None and (
            type(self.separators) is not tuple
            or len(self.separators) != 2
            or any(type(value) is not str for value in self.separators)
        ):
            raise TypeError("separators must be a pair of strings or null")
        if type(self.terminal_newline) is not bool:
            raise TypeError("terminal_newline must be a boolean")

    @classmethod
    def canonical(cls, *, limits: JsonLimits) -> JsonSerializer:
        return cls(
            limits=limits,
            ensure_ascii=False,
            sort_keys=True,
            allow_non_finite=False,
            indent=None,
            separators=(",", ":"),
            terminal_newline=False,
        )

    @classmethod
    def durable_pretty(
        cls,
        *,
        limits: JsonLimits,
        sort_keys: bool,
    ) -> JsonSerializer:
        return cls(
            limits=limits,
            ensure_ascii=False,
            sort_keys=sort_keys,
            allow_non_finite=False,
            indent=2,
            separators=None,
            terminal_newline=True,
        )

    def serialize_text(self, value: JsonValue) -> str:
        projected = JsonValueProjector(
            self.limits,
            allow_non_finite=self.allow_non_finite,
        ).project(value)
        try:
            if self.separators is None:
                text = json.dumps(
                    projected,
                    allow_nan=self.allow_non_finite,
                    ensure_ascii=self.ensure_ascii,
                    indent=self.indent,
                    sort_keys=self.sort_keys,
                )
            else:
                text = json.dumps(
                    projected,
                    allow_nan=self.allow_non_finite,
                    ensure_ascii=self.ensure_ascii,
                    indent=self.indent,
                    separators=self.separators,
                    sort_keys=self.sort_keys,
                )
            if self.terminal_newline:
                text += "\n"
            encoded = text.encode("utf-8", errors="strict")
        except (
            RecursionError,
            TypeError,
            UnicodeError,
            ValueError,
        ) as error:
            raise JsonSerializationError(
                f"could not serialize JSON: {error}"
            ) from error
        if len(encoded) > self.limits.maximum_utf8_bytes:
            raise JsonLimitError("serialized JSON exceeds its byte limit")
        return text

    def serialize_bytes(self, value: JsonValue) -> bytes:
        return self.serialize_text(value).encode("utf-8", errors="strict")
