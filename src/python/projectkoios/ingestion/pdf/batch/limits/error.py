"""PDF batch resource-limit failures."""


class PdfBatchLimitError(ValueError):
    """A PDF batch record or wire document exceeded a declared bound."""
