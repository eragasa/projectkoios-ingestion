"""Request to durably publish one exact extraction decomposition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import ExtractionResult
from projectkoios.ingestion.serialization import serialize_contract


@dataclass(frozen=True, slots=True)
class ExtractionPublicationRequest(
    AbstractImmutableDataObject,
    DataObjectActionRequest,
):
    """One create-once extraction publication request."""

    CONTRACT_NAME: ClassVar[str] = "extraction-publication-request"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    request_id: str
    extraction: ExtractionResult

    @classmethod
    def create(
        cls,
        *,
        extraction: ExtractionResult,
    ) -> ExtractionPublicationRequest:
        if type(extraction) is not ExtractionResult:
            raise TypeError("extraction must be an ExtractionResult")
        payload = serialize_contract(extraction).encode("utf-8")
        return cls(
            request_id=stable_id(
                "extraction-publication-request",
                cls.CONTRACT_VERSION,
                extraction.document.document_id,
                extraction.manifest.manifest_id,
                payload,
            ),
            extraction=extraction,
        )

    def __post_init__(self) -> None:
        if type(self.extraction) is not ExtractionResult:
            raise TypeError("extraction must be an ExtractionResult")
        payload = serialize_contract(self.extraction).encode("utf-8")
        expected = stable_id(
            "extraction-publication-request",
            self.CONTRACT_VERSION,
            self.extraction.document.document_id,
            self.extraction.manifest.manifest_id,
            payload,
        )
        if self.request_id != expected:
            raise ValueError(
                "extraction publication request ID is inconsistent"
            )
