from __future__ import annotations

import projectkoios.ingestion as legacy_ingestion
import projectkoios.ingestion.ocr as legacy_ocr
import projectkoios.ingestion.tesseract as legacy_tesseract
import pytest
from projectkoios.ingestion.ocr.models import (
    OcrProcessorIdentity,
    OcrRequest,
    OcrResult,
)
from projectkoios.ingestion.ocr.processors.base import BaseOcrProcessor
from projectkoios.ingestion.ocr.processors.ocr import (
    OcrProcessor,
    PilotOcrProcessor,
)
from projectkoios.ingestion.ocr.processors.tesseract.processor import (
    TesseractOcrProcessor,
)


def test__ocr_models__use_canonical_Ocr_names() -> None:
    assert OcrRequest.__module__ == "projectkoios.ingestion.ocr.models"
    assert OcrResult.__module__ == "projectkoios.ingestion.ocr.models"


def test__OcrProcessor__is_a_base_processor_facade() -> None:
    assert issubclass(OcrProcessor, BaseOcrProcessor)
    assert issubclass(TesseractOcrProcessor, BaseOcrProcessor)
    assert TesseractOcrProcessor.__module__ == (
        "projectkoios.ingestion.ocr.processors.tesseract.processor"
    )
    assert PilotOcrProcessor is OcrProcessor


@pytest.mark.parametrize(
    ("legacy_name", "canonical"),
    (
        ("OCRProcessorIdentity", OcrProcessorIdentity),
        ("OCRRequest", OcrRequest),
        ("OCRResult", OcrResult),
    ),
)
def test__legacy_ocr_model_names__emit_deprecation_warning(
    legacy_name: str,
    canonical: type[object],
) -> None:
    with pytest.warns(DeprecationWarning, match="is deprecated"):
        legacy = getattr(legacy_ocr, legacy_name)

    assert legacy is canonical


def test__legacy_tesseract_processor_name__emits_deprecation_warning() -> None:
    with pytest.warns(DeprecationWarning, match="is deprecated"):
        legacy = legacy_tesseract.TesseractOCRProcessor

    assert legacy is TesseractOcrProcessor


def test__top_level_legacy_OCRRequest__emits_deprecation_warning() -> None:
    with pytest.warns(DeprecationWarning, match="is deprecated"):
        legacy = legacy_ingestion.OCRRequest

    assert legacy is OcrRequest
