from __future__ import annotations

from importlib import import_module
from typing import Any
from warnings import warn

_TARGETS = {
    "TESSERACT_ADAPTER_VERSION": (
        "projectkoios.ingestion.ocr.processors.tesseract.constants",
        "TESSERACT_ADAPTER_VERSION",
    ),
    "TesseractAdapterConfiguration": (
        "projectkoios.ingestion.ocr.processors.tesseract.models",
        "TesseractAdapterConfiguration",
    ),
    "TesseractAdapterConfigurationError": (
        "projectkoios.ingestion.ocr.processors.tesseract.errors",
        "TesseractAdapterConfigurationError",
    ),
    "TesseractLanguageBinding": (
        "projectkoios.ingestion.ocr.processors.tesseract.models",
        "TesseractLanguageBinding",
    ),
    "TesseractOcrProcessor": (
        "projectkoios.ingestion.ocr.processors.tesseract.processor",
        "TesseractOcrProcessor",
    ),
    "TesseractOCRProcessor": (
        "projectkoios.ingestion.ocr.processors.tesseract.processor",
        "TesseractOcrProcessor",
    ),
}


def __getattr__(name: str) -> Any:
    target = _TARGETS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute_name = target
    warn(
        f"projectkoios.ingestion.tesseract.{name} is deprecated; "
        f"import {attribute_name} from {module_name}",
        DeprecationWarning,
        stacklevel=2,
    )
    return getattr(import_module(module_name), attribute_name)
