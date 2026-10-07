"""LayoutParser adaptation limit failures."""


class LayoutParserLimitError(ValueError):
    """Raised before excessive LayoutParser evidence is retained or hashed."""
