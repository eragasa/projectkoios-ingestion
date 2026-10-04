"""Deterministic OCR cache identity."""

from __future__ import annotations

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.ocr import _primitives as primitives
from projectkoios.ingestion.ocr.constants import OCR_CONTRACT_VERSION
from projectkoios.ingestion.ocr.processor_identity import OCRProcessorIdentity
from projectkoios.ingestion.ocr.request import OCRRequest


def build_ocr_cache_key(
    *,
    request: OCRRequest,
    processor_identity: OCRProcessorIdentity,
    contract_version: str = OCR_CONTRACT_VERSION,
) -> str:
    """Build the complete derived-cache identity without storing a result."""
    primitives._bounded_string(
        "OCR contract version",
        contract_version,
        request.configuration.max_identity_field_characters,
        nonempty=True,
    )
    if not isinstance(processor_identity, OCRProcessorIdentity):
        raise TypeError("processor_identity must be an OCRProcessorIdentity")
    processor_identity.validate_for(request)
    return stable_id(
        "ocr-cache",
        contract_version,
        tuple(selection.identity_parts() for selection in request.selections),
        request.configuration.identity_parts(),
        processor_identity.identity_parts(),
    )
