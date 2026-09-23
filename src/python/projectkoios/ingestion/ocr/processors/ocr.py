from __future__ import annotations

from projectkoios.ingestion.ocr.models import (
    OcrProcessorIdentity,
    OcrRequest,
    OcrResult,
)
from projectkoios.ingestion.ocr.processors.base import BaseOcrProcessor
from projectkoios.ingestion.ocr.processors.tesseract.processor import (
    TesseractOcrProcessor,
)


class OcrProcessor(BaseOcrProcessor):
    """OCR facade that encapsulates the configured Tesseract adapter."""

    def __init__(self, processor: TesseractOcrProcessor) -> None:
        if not isinstance(processor, TesseractOcrProcessor):
            raise TypeError("processor must be a TesseractOcrProcessor")
        self.processor = processor
        self.name = processor.name
        self.version = processor.version

    def identity_for(self, request: OcrRequest) -> OcrProcessorIdentity:
        return self.processor.identity_for(request)

    def process(self, request: OcrRequest) -> OcrResult:
        return self.processor.process(request)


PilotOcrProcessor = OcrProcessor

__all__ = ["OcrProcessor", "PilotOcrProcessor"]
