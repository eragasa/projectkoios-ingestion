"""OCRReconciliationRequest reconciliation domain object."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.layout import PageLayoutResult
from projectkoios.ingestion.models import ExtractedPage
from projectkoios.ingestion.ocr.result import OCRResult
from projectkoios.ingestion.ocr.selection import OCRSelection
from projectkoios.ingestion.ocr.selection_result import OCRSelectionResult
from projectkoios.ingestion.reconciliation import _identity as identity
from projectkoios.ingestion.reconciliation import _primitives as primitives
from projectkoios.ingestion.reconciliation import _validation as validation
from projectkoios.ingestion.reconciliation.configuration import (
    OCRReconciliationConfiguration,
)
from projectkoios.ingestion.reconciliation.constants import (
    OCR_RECONCILIATION_CONTRACT_VERSION,
)


@dataclass(frozen=True)
class OCRReconciliationRequest(
    AbstractImmutableDataObject, DataObjectActionRequest
):
    input_id: str
    ocr_result: OCRResult
    selection_index: int
    native_page: ExtractedPage | None
    layout_result: PageLayoutResult | None
    configuration: OCRReconciliationConfiguration
    contract_version: str = OCR_RECONCILIATION_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        ocr_result: OCRResult,
        selection_index: int,
        native_page: ExtractedPage | None = None,
        layout_result: PageLayoutResult | None = None,
        configuration: OCRReconciliationConfiguration | None = None,
    ) -> OCRReconciliationRequest:
        config = configuration or OCRReconciliationConfiguration()
        validation._validate_input_parts(
            ocr_result,
            selection_index,
            native_page,
            layout_result,
            config,
        )
        input_id = identity._input_id(
            ocr_result,
            selection_index,
            native_page,
            layout_result,
            config,
        )
        return cls(
            input_id=input_id,
            ocr_result=ocr_result,
            selection_index=selection_index,
            native_page=native_page,
            layout_result=layout_result,
            configuration=config,
        )

    def __post_init__(self) -> None:
        if self.contract_version != OCR_RECONCILIATION_CONTRACT_VERSION:
            raise ValueError("unsupported OCR reconciliation input version")
        primitives._bounded_string("reconciliation input ID", self.input_id)
        validation._validate_input_parts(
            self.ocr_result,
            self.selection_index,
            self.native_page,
            self.layout_result,
            self.configuration,
        )
        expected = identity._input_id(
            self.ocr_result,
            self.selection_index,
            self.native_page,
            self.layout_result,
            self.configuration,
        )
        if self.input_id != expected:
            raise ValueError("OCR reconciliation input ID is inconsistent")

    @property
    def request_id(self) -> str:
        """Return the established input identity as the request identity."""
        return self.input_id

    @property
    def selection(self) -> OCRSelection:
        return self.ocr_result.request.selections[self.selection_index]

    @property
    def selection_result(self) -> OCRSelectionResult:
        return self.ocr_result.selection_results[self.selection_index]
