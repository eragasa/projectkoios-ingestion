"""Layout-region proposal limit errors."""

from projectkoios.ingestion.layout.limits.error import LayoutLimitError


class LayoutProposalLimitError(LayoutLimitError):
    """Reject proposal evidence outside explicit implementation bounds."""
