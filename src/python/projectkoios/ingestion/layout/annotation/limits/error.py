"""Layout annotation limit errors."""

from projectkoios.ingestion.layout.limits.error import LayoutLimitError


class LayoutAnnotationLimitError(LayoutLimitError):
    """Reject annotation evidence outside explicit implementation bounds."""
