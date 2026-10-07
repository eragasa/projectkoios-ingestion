"""JSON resource-limit failure."""


class JsonLimitError(ValueError):
    """Raised when a JSON operation exceeds an explicit resource bound."""
