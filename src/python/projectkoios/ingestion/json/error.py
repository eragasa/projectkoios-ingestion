"""Shared JSON parse and serialization failures."""


class JsonError(ValueError):
    """Base failure for a non-limit JSON boundary violation."""


class JsonParseError(JsonError):
    """Raised when input is not valid strict bounded JSON."""


class JsonSerializationError(JsonError):
    """Raised when a value cannot be represented as bounded JSON."""
