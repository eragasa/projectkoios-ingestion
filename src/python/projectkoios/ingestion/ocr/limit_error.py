"""OCRContractLimitError OCR domain object."""

from __future__ import annotations


class OCRContractLimitError(ValueError):
    """Raised when an OCR request or result exceeds configured bounds."""
