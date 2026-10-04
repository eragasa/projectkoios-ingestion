"""Nominal OCR-reconciliation boundary."""

from __future__ import annotations

from abc import ABC, abstractmethod

from projectkoios.ingestion.reconciliation.request import (
    OCRReconciliationRequest,
)
from projectkoios.ingestion.reconciliation.result import OCRReconciliationResult


class OCRReconciler(ABC):
    """Propose relationships without replacing native or OCR evidence."""

    __slots__ = ()

    name: str
    version: str

    @abstractmethod
    def reconcile(
        self, reconciliation_input: OCRReconciliationRequest
    ) -> OCRReconciliationResult:
        """Reconcile one complete native/OCR evidence request."""
