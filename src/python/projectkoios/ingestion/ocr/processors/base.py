from __future__ import annotations

from abc import ABC, abstractmethod

from projectkoios.ingestion.ocr.models import (
    OcrProcessorIdentity,
    OcrRequest,
    OcrResult,
)


class BaseOcrProcessor(ABC):
    name: str
    version: str

    @abstractmethod
    def identity_for(self, request: OcrRequest) -> OcrProcessorIdentity:
        raise NotImplementedError

    @abstractmethod
    def process(self, request: OcrRequest) -> OcrResult:
        raise NotImplementedError


__all__ = ["BaseOcrProcessor"]
