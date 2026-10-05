"""OCRSelectionResult OCR domain object."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.ocr import _identity as identity
from projectkoios.ingestion.ocr import _primitives as primitives
from projectkoios.ingestion.ocr import _validation as validation
from projectkoios.ingestion.ocr.configuration import OCRConfiguration
from projectkoios.ingestion.ocr.constants import OCR_CONTRACT_VERSION
from projectkoios.ingestion.ocr.failure import OCRFailure
from projectkoios.ingestion.ocr.limit_error import OCRContractLimitError
from projectkoios.ingestion.ocr.line import OCRLine
from projectkoios.ingestion.ocr.selection import OCRSelection
from projectkoios.ingestion.ocr.selection_status import OCRSelectionStatus
from projectkoios.ingestion.ocr.token import OCRToken
from projectkoios.ingestion.ocr.warning import OCRWarning


@dataclass(frozen=True)
class OCRSelectionResult(AbstractImmutableDataObject):
    """Completed, partial, or failed evidence for exactly one selection."""

    selection_result_id: str
    selection_id: str
    image_id: str
    status: OCRSelectionStatus
    tokens: tuple[OCRToken, ...]
    lines: tuple[OCRLine, ...]
    warnings: tuple[OCRWarning, ...]
    failure: OCRFailure | None
    configuration_digest: str
    processor_name: str
    processor_version: str
    backend_name: str
    backend_version: str
    contract_version: str = OCR_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        selection: OCRSelection,
        configuration: OCRConfiguration,
        status: OCRSelectionStatus,
        tokens: tuple[OCRToken, ...] = (),
        lines: tuple[OCRLine, ...] = (),
        warnings: tuple[OCRWarning, ...] = (),
        failure: OCRFailure | None = None,
        processor_name: str,
        processor_version: str,
        backend_name: str,
        backend_version: str,
    ) -> OCRSelectionResult:
        if not isinstance(status, OCRSelectionStatus):
            raise ValueError("OCR selection status is unsupported")
        primitives._require_identity_fields(
            selection.selection_id,
            selection.image.image_id,
            configuration.configuration_digest,
            processor_name,
            processor_version,
            backend_name,
            backend_version,
        )
        for name, values, limit in (
            ("tokens", tokens, configuration.max_tokens_per_selection),
            ("lines", lines, configuration.max_lines_per_selection),
            ("warnings", warnings, configuration.max_warnings_per_selection),
        ):
            primitives._require_tuple(name, values)
            if len(values) > limit:
                raise OCRContractLimitError(
                    f"{name} exceed their configured per-selection limit"
                )
        result_id = identity._ocr_selection_result_id(
            selection.selection_id,
            selection.image.image_id,
            status,
            tokens,
            lines,
            warnings,
            failure,
            configuration.configuration_digest,
            processor_name,
            processor_version,
            backend_name,
            backend_version,
        )
        result = cls(
            selection_result_id=result_id,
            selection_id=selection.selection_id,
            image_id=selection.image.image_id,
            status=status,
            tokens=tokens,
            lines=lines,
            warnings=warnings,
            failure=failure,
            configuration_digest=configuration.configuration_digest,
            processor_name=processor_name,
            processor_version=processor_version,
            backend_name=backend_name,
            backend_version=backend_version,
        )
        validation._validate_selection_result(result, selection, configuration)
        return result

    def __post_init__(self) -> None:
        if self.contract_version != OCR_CONTRACT_VERSION:
            raise ValueError("unsupported OCR selection result version")
        for name in ("tokens", "lines", "warnings"):
            primitives._require_tuple(name, getattr(self, name))
        if not isinstance(self.status, OCRSelectionStatus):
            raise ValueError("OCR selection status is unsupported")
        primitives._require_identity_fields(
            self.selection_id,
            self.image_id,
            self.configuration_digest,
            self.processor_name,
            self.processor_version,
            self.backend_name,
            self.backend_version,
        )
        validation._validate_selection_result_intrinsic(self)
        expected = identity._ocr_selection_result_id(
            self.selection_id,
            self.image_id,
            self.status,
            self.tokens,
            self.lines,
            self.warnings,
            self.failure,
            self.configuration_digest,
            self.processor_name,
            self.processor_version,
            self.backend_name,
            self.backend_version,
        )
        if self.selection_result_id != expected:
            raise ValueError(
                "OCR selection result ID does not match its evidence"
            )
