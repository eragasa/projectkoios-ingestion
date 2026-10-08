"""Shared JSON parse and serialization failures."""


class JsonError(ValueError):
    """Base failure for a non-limit JSON boundary violation."""


class JsonParseError(JsonError):
    """Raised when input is not valid strict bounded JSON."""


class JsonDuplicateFieldError(JsonParseError):
    """Raised when one JSON object repeats a field name."""


class JsonSerializationError(JsonError):
    """Raised when a value cannot be represented as bounded JSON."""
