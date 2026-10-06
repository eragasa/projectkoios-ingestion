"""Nominal OCR processor boundary."""

from __future__ import annotations

from abc import ABC, abstractmethod

from projectkoios.ingestion.ocr.identity.processor import OCRProcessorIdentity
from projectkoios.ingestion.ocr.request import OCRRequest
from projectkoios.ingestion.ocr.result.ocr import OCRResult


class OCRProcessor(ABC):
    """Execute OCR through a concrete adapter without accepting its text."""

    __slots__ = ()

    name: str
    version: str

    @abstractmethod
    def identity_for(self, request: OCRRequest) -> OCRProcessorIdentity:
        """Return the exact processor identity for a request."""

    @abstractmethod
    def action(self, *, request: OCRRequest) -> OCRResult:
        """Execute one complete OCR action request."""

    @abstractmethod
    def process(self, request: OCRRequest) -> OCRResult:
        """Process one complete OCR request."""
