"""OCRRequest OCR domain object."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from itertools import islice

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.ocr import _identity as identity
from projectkoios.ingestion.ocr import _primitives as primitives
from projectkoios.ingestion.ocr import _validation as validation
from projectkoios.ingestion.ocr.configuration import OCRConfiguration
from projectkoios.ingestion.ocr.constants import OCR_CONTRACT_VERSION
from projectkoios.ingestion.ocr.limit_error import OCRContractLimitError
from projectkoios.ingestion.ocr.selection import OCRSelection


@dataclass(frozen=True)
class OCRRequest(AbstractImmutableDataObject, DataObjectActionRequest):
    """A non-empty, ordered, bounded OCR request."""

    request_id: str
    selections: tuple[OCRSelection, ...]
    configuration: OCRConfiguration
    contract_version: str = OCR_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        selections: Iterable[OCRSelection],
        *,
        configuration: OCRConfiguration | None = None,
    ) -> OCRRequest:
        config = configuration or OCRConfiguration()
        bounded = tuple(islice(selections, config.max_selections + 1))
        if len(bounded) > config.max_selections:
            raise OCRContractLimitError(
                "selection count exceeds max_selections"
            )
        validation._preflight_request(bounded, config)
        return cls(
            request_id=identity._ocr_request_id(bounded, config),
            selections=bounded,
            configuration=config,
        )

    def __post_init__(self) -> None:
        if self.contract_version != OCR_CONTRACT_VERSION:
            raise ValueError("unsupported OCR request contract version")
        primitives._require_tuple("selections", self.selections)
        if not isinstance(self.configuration, OCRConfiguration):
            raise TypeError("configuration must be an OCRConfiguration")
        validation._preflight_request(self.selections, self.configuration)
        if self.request_id != identity._ocr_request_id(
            self.selections, self.configuration
        ):
            raise ValueError("OCR request ID does not match its evidence")
