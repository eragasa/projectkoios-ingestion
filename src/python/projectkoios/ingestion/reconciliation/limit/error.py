"""OCRReconciliationLimitError reconciliation domain object."""

from __future__ import annotations


class OCRReconciliationLimitError(ValueError):
    """Raised before reconciliation work exceeds a configured hard bound."""
