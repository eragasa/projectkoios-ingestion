"""JSON resource-limit failure."""


class JsonLimitError(ValueError):
    """Raised when a JSON operation exceeds an explicit resource bound."""


class JsonDocumentByteLimitError(JsonLimitError):
    """Raised when a complete JSON document exceeds its byte ceiling."""
