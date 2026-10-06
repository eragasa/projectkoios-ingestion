"""Typed source-extraction failure at the bounded-freeze boundary."""


class FreezableSourceExtractionError(RuntimeError):
    """Report invalid source evidence rejected by a freezable extractor."""
