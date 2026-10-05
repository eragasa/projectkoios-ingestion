"""OCRResult OCR domain object."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.ocr import _identity as identity
from projectkoios.ingestion.ocr import _primitives as primitives
from projectkoios.ingestion.ocr import _validation as validation
from projectkoios.ingestion.ocr.cache_key import build_ocr_cache_key
from projectkoios.ingestion.ocr.constants import OCR_CONTRACT_VERSION
from projectkoios.ingestion.ocr.limit_error import OCRContractLimitError
from projectkoios.ingestion.ocr.processor_identity import OCRProcessorIdentity
from projectkoios.ingestion.ocr.request import OCRRequest
from projectkoios.ingestion.ocr.result_status import OCRResultStatus
from projectkoios.ingestion.ocr.selection_result import OCRSelectionResult


@dataclass(frozen=True)
class OCRResult(AbstractImmutableDataObject, DataObjectActionResult):
    """Ordered OCR outcomes retaining their complete bounded request."""

    result_id: str
    request: OCRRequest
    selection_results: tuple[OCRSelectionResult, ...]
    status: OCRResultStatus
    cache_key: str
    processor_identity: OCRProcessorIdentity
    contract_version: str = OCR_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        request: OCRRequest,
        selection_results: tuple[OCRSelectionResult, ...],
        processor_identity: OCRProcessorIdentity,
    ) -> OCRResult:
        if not isinstance(processor_identity, OCRProcessorIdentity):
            raise TypeError(
                "processor_identity must be an OCRProcessorIdentity"
            )
        processor_identity.validate_for(request)
        primitives._require_tuple("selection_results", selection_results)
        validation._preflight_result_counts(request, selection_results)
        status = validation._overall_status(selection_results)
        cache_key = build_ocr_cache_key(
            request=request,
            processor_identity=processor_identity,
        )
        primitives._validate_contract_size(
            (
                request,
                selection_results,
                status,
                cache_key,
                processor_identity,
            ),
            request.configuration.max_result_bytes,
        )
        result_id = identity._ocr_result_id(
            request,
            selection_results,
            status,
            cache_key,
            processor_identity.processor_name,
            processor_identity.processor_version,
            processor_identity.backend_name,
            processor_identity.backend_version,
        )
        return cls(
            result_id=result_id,
            request=request,
            selection_results=selection_results,
            status=status,
            cache_key=cache_key,
            processor_identity=processor_identity,
        )

    @property
    def processor_name(self) -> str:
        return self.processor_identity.processor_name

    @property
    def processor_version(self) -> str:
        return self.processor_identity.processor_version

    @property
    def backend_name(self) -> str:
        return self.processor_identity.backend_name

    @property
    def backend_version(self) -> str:
        return self.processor_identity.backend_version

    def __post_init__(self) -> None:
        if self.contract_version != OCR_CONTRACT_VERSION:
            raise ValueError("unsupported OCR result contract version")
        if not isinstance(self.request, OCRRequest):
            raise TypeError("request must be an OCRRequest")
        if not isinstance(self.processor_identity, OCRProcessorIdentity):
            raise TypeError(
                "processor_identity must be an OCRProcessorIdentity"
            )
        self.processor_identity.validate_for(self.request)
        primitives._require_tuple("selection_results", self.selection_results)
        config = self.request.configuration
        if len(self.selection_results) != len(self.request.selections):
            raise ValueError("every OCR selection must have exactly one result")

        validation._preflight_result_counts(
            self.request, self.selection_results
        )
        total_text = sum(
            sum(len(token.text) for token in item.tokens)
            + sum(len(line.text) for line in item.lines)
            for item in self.selection_results
        )
        if total_text > config.max_total_text_characters:
            raise OCRContractLimitError(
                "text length exceeds max_total_text_characters"
            )

        for selection, selection_result in zip(
            self.request.selections, self.selection_results, strict=True
        ):
            validation._validate_selection_result(
                selection_result, selection, config
            )
            primitives._same_processor_identity(self, selection_result)
        expected_status = validation._overall_status(self.selection_results)
        if self.status is not expected_status:
            raise ValueError(
                "overall OCR status contradicts selection statuses"
            )
        expected_cache_key = build_ocr_cache_key(
            request=self.request,
            processor_identity=self.processor_identity,
        )
        if self.cache_key != expected_cache_key:
            raise ValueError("OCR cache key does not match request evidence")
        primitives._validate_contract_size(self, config.max_result_bytes)
        expected_id = identity._ocr_result_id(
            self.request,
            self.selection_results,
            self.status,
            self.cache_key,
            self.processor_name,
            self.processor_version,
            self.backend_name,
            self.backend_version,
        )
        if self.result_id != expected_id:
            raise ValueError("OCR result ID does not match its evidence")
