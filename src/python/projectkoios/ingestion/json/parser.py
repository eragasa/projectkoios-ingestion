"""Strict bounded UTF-8 JSON parsing."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any

from projectkoios.ingestion.json.error import (
    JsonParseError,
    JsonSerializationError,
)
from projectkoios.ingestion.json.limits.definition import JsonLimits
from projectkoios.ingestion.json.limits.error import JsonLimitError
from projectkoios.ingestion.json.value import JsonValue, JsonValueProjector


@dataclass(frozen=True, slots=True)
class JsonParser:
    """Parse one strict bounded JSON value from UTF-8 bytes or text."""

    limits: JsonLimits

    def parse_bytes(self, content: bytes) -> JsonValue:
        if not isinstance(content, bytes):
            raise TypeError("JSON content must be bytes")
        if len(content) > self.limits.maximum_utf8_bytes:
            raise JsonLimitError("JSON content exceeds its byte limit")
        try:
            text = content.decode("utf-8", errors="strict")
        except UnicodeError as error:
            raise JsonParseError("JSON content is not valid UTF-8") from error
        return self._parse(text)

    def parse_text(self, content: str) -> JsonValue:
        if not isinstance(content, str):
            raise TypeError("JSON content must be text")
        try:
            encoded = content.encode("utf-8", errors="strict")
        except UnicodeError as error:
            raise JsonParseError("JSON content is not valid UTF-8") from error
        if len(encoded) > self.limits.maximum_utf8_bytes:
            raise JsonLimitError("JSON content exceeds its byte limit")
        return self._parse(content)

    def _parse(self, text: str) -> JsonValue:
        self._require_lexical_bounds(text)

        def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise JsonParseError(
                        "JSON object contains a duplicate field"
                    )
                result[key] = value
            return result

        def parse_constant(value: str) -> object:
            raise JsonParseError(f"forbidden JSON constant: {value}")

        def parse_integer(value: str) -> int:
            if len(value.lstrip("-")) > self.limits.maximum_number_characters:
                raise JsonLimitError("JSON integer exceeds its character limit")
            try:
                return int(value)
            except ValueError as error:
                raise JsonParseError("JSON integer is malformed") from error

        def parse_float(value: str) -> float:
            if len(value) > self.limits.maximum_number_characters:
                raise JsonLimitError("JSON number exceeds its character limit")
            try:
                parsed = float(value)
            except ValueError as error:
                raise JsonParseError("JSON number is malformed") from error
            if not math.isfinite(parsed):
                raise JsonParseError("JSON number must be finite")
            return parsed

        try:
            value = json.loads(
                text,
                object_pairs_hook=object_pairs,
                parse_constant=parse_constant,
                parse_int=parse_integer,
                parse_float=parse_float,
            )
            return JsonValueProjector(self.limits).project(value)
        except JsonLimitError:
            raise
        except JsonParseError:
            raise
        except JsonSerializationError as error:
            raise JsonParseError(str(error)) from error
        except (
            json.JSONDecodeError,
            OverflowError,
            RecursionError,
            TypeError,
            ValueError,
        ) as error:
            raise JsonParseError(f"invalid JSON: {error}") from error

    def _require_lexical_bounds(self, text: str) -> None:
        depth = 0
        in_string = False
        escaped = False
        for character in text:
            if in_string:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == '"':
                    in_string = False
                continue
            if character == '"':
                in_string = True
            elif character in "[{":
                depth += 1
                if depth > self.limits.maximum_container_depth:
                    raise JsonLimitError(
                        "JSON container depth exceeds its limit"
                    )
            elif character in "]}":
                depth -= 1
                if depth < 0:
                    raise JsonParseError("JSON containers are unbalanced")
        if depth != 0:
            raise JsonParseError("JSON containers are unbalanced")
