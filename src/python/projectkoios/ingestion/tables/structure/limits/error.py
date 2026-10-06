"""TableStructureLimitError table-structure domain object."""

from __future__ import annotations


class TableStructureLimitError(ValueError):
    """Raised before reconstruction exceeds a configured hard bound."""
