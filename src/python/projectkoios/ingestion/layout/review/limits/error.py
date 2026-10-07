"""Layout review limit errors."""

from projectkoios.ingestion.layout.limits.error import LayoutLimitError


class LayoutReviewLimitError(LayoutLimitError):
    """Reject a layout review value outside explicit implementation bounds."""
