"""OCRReconciliationResult reconciliation domain object."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.ocr.line import OCRLine
from projectkoios.ingestion.reconciliation import _identity as identity
from projectkoios.ingestion.reconciliation import _primitives as primitives
from projectkoios.ingestion.reconciliation import _validation as validation
from projectkoios.ingestion.reconciliation.constants import (
    OCR_RECONCILIATION_CONTRACT_VERSION,
)
from projectkoios.ingestion.reconciliation.item import OCRReconciledItem
from projectkoios.ingestion.reconciliation.match import OCRReconciliationMatch
from projectkoios.ingestion.reconciliation.native_block_evidence import (
    OCRNativeBlockEvidence,
)
from projectkoios.ingestion.reconciliation.native_line_segment import (
    OCRNativeLineSegment,
)
from projectkoios.ingestion.reconciliation.request import (
    OCRReconciliationRequest,
)
from projectkoios.ingestion.reconciliation.stream_choice import (
    OCRReconciliationStreamChoice,
)
from projectkoios.ingestion.reconciliation.warning import (
    OCRReconciliationWarning,
)


@dataclass(frozen=True)
class OCRReconciliationResult(
    AbstractImmutableDataObject, DataObjectActionResult
):
    result_id: str
    reconciliation_input: OCRReconciliationRequest
    native_stream: tuple[OCRNativeBlockEvidence, ...]
    native_segments: tuple[OCRNativeLineSegment, ...]
    ocr_stream: tuple[OCRLine, ...]
    matches: tuple[OCRReconciliationMatch, ...]
    proposed_merged_stream: tuple[OCRReconciledItem, ...]
    warnings: tuple[OCRReconciliationWarning, ...]
    processor_name: str
    processor_version: str
    configuration_digest: str
    contract_version: str = OCR_RECONCILIATION_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        reconciliation_input: OCRReconciliationRequest,
        native_stream: tuple[OCRNativeBlockEvidence, ...],
        native_segments: tuple[OCRNativeLineSegment, ...],
        ocr_stream: tuple[OCRLine, ...],
        matches: tuple[OCRReconciliationMatch, ...],
        proposed_merged_stream: tuple[OCRReconciledItem, ...],
        warnings: tuple[OCRReconciliationWarning, ...],
        processor_name: str,
        processor_version: str,
    ) -> OCRReconciliationResult:
        if not isinstance(reconciliation_input, OCRReconciliationRequest):
            raise TypeError("reconciliation_input has the wrong type")
        configuration_digest = (
            reconciliation_input.configuration.configuration_digest
        )
        validation._preflight_result_collections(
            reconciliation_input,
            native_stream,
            native_segments,
            ocr_stream,
            matches,
            proposed_merged_stream,
            warnings,
        )
        result_id = identity._result_id(
            reconciliation_input.input_id,
            native_stream,
            native_segments,
            ocr_stream,
            matches,
            proposed_merged_stream,
            warnings,
            processor_name,
            processor_version,
            configuration_digest,
        )
        return cls(
            result_id=result_id,
            reconciliation_input=reconciliation_input,
            native_stream=native_stream,
            native_segments=native_segments,
            ocr_stream=ocr_stream,
            matches=matches,
            proposed_merged_stream=proposed_merged_stream,
            warnings=warnings,
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=configuration_digest,
        )

    def __post_init__(self) -> None:
        if self.contract_version != OCR_RECONCILIATION_CONTRACT_VERSION:
            raise ValueError("unsupported OCR reconciliation result version")
        if not isinstance(self.reconciliation_input, OCRReconciliationRequest):
            raise TypeError("reconciliation_input has the wrong type")
        for name in (
            "native_stream",
            "native_segments",
            "ocr_stream",
            "matches",
            "proposed_merged_stream",
            "warnings",
        ):
            primitives._require_tuple(name, getattr(self, name))
        validation._validate_result(self)
        expected = identity._result_id(
            self.reconciliation_input.input_id,
            self.native_stream,
            self.native_segments,
            self.ocr_stream,
            self.matches,
            self.proposed_merged_stream,
            self.warnings,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        )
        if self.result_id != expected:
            raise ValueError("OCR reconciliation result ID is inconsistent")

    @property
    def request(self) -> OCRReconciliationRequest:
        """Return the exact request retained by this result."""
        return self.reconciliation_input

    @property
    def request_id(self) -> str:
        return self.reconciliation_input.request_id

    @property
    def actionizer_name(self) -> str:
        return self.processor_name

    @property
    def actionizer_version(self) -> str:
        return self.processor_version

    def stream(
        self, choice: OCRReconciliationStreamChoice
    ) -> (
        tuple[OCRNativeBlockEvidence, ...]
        | tuple[OCRLine, ...]
        | tuple[OCRReconciledItem, ...]
    ):
        if choice is OCRReconciliationStreamChoice.NATIVE:
            return self.native_stream
        if choice is OCRReconciliationStreamChoice.OCR:
            return self.ocr_stream
        if choice is OCRReconciliationStreamChoice.PROPOSED_MERGED:
            return self.proposed_merged_stream
        raise ValueError("unsupported OCR reconciliation stream choice")
