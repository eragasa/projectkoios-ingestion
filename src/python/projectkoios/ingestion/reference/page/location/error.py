"""Reference page-location failures."""


class ReferenceLocatorError(ValueError):
    """Base failure for bounded reference-page location."""


class ReferenceLocatorVerificationError(ReferenceLocatorError):
    """Raised when supplied evidence does not form one exact lineage."""
