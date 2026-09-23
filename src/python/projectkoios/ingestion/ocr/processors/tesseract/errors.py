from __future__ import annotations


class TesseractAdapterConfigurationError(ValueError):
    """Raised when adapter construction is invalid or exceeds hard bounds."""


__all__ = ["TesseractAdapterConfigurationError"]
