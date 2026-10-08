"""Reference page-location resource-limit failure."""

from projectkoios.ingestion.reference.page.location.error import (
    ReferenceLocatorError,
)


class ReferenceLocatorLimitError(ReferenceLocatorError):
    """Raised before locator processing exceeds a hard bound."""
