from __future__ import annotations

from importlib import import_module
from typing import Any
from warnings import warn

_RENAMED_MODELS = {
    "OCRProcessorIdentity": "OcrProcessorIdentity",
    "OCRRequest": "OcrRequest",
    "OCRResult": "OcrResult",
}
_PROCESSOR_EXPORTS = {
    "BaseOcrProcessor": (
        "projectkoios.ingestion.ocr.processors.base",
        "BaseOcrProcessor",
    ),
    "OcrProcessor": (
        "projectkoios.ingestion.ocr.processors.ocr",
        "OcrProcessor",
    ),
    "PilotOcrProcessor": (
        "projectkoios.ingestion.ocr.processors.ocr",
        "PilotOcrProcessor",
    ),
    "TesseractOcrProcessor": (
        "projectkoios.ingestion.ocr.processors.tesseract.processor",
        "TesseractOcrProcessor",
    ),
}


def __getattr__(name: str) -> Any:
    processor_target = _PROCESSOR_EXPORTS.get(name)
    if processor_target is not None:
        module_name, attribute_name = processor_target
    else:
        module_name = "projectkoios.ingestion.ocr.models"
        attribute_name = _RENAMED_MODELS.get(name, name)
        module = import_module(module_name)
        if not hasattr(module, attribute_name):
            raise AttributeError(name)
        warn(
            f"projectkoios.ingestion.ocr.{name} is deprecated; "
            f"import {attribute_name} from {module_name}",
            DeprecationWarning,
            stacklevel=2,
        )
        return getattr(module, attribute_name)
    warn(
        f"projectkoios.ingestion.ocr.{name} is deprecated; "
        f"import {attribute_name} from {module_name}",
        DeprecationWarning,
        stacklevel=2,
    )
    return getattr(import_module(module_name), attribute_name)
