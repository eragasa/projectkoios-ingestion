"""Backend-neutral canonical reading-evidence source results."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.base.actionizer.result import (
    AbstractDataObjectActionResult,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.transcript.reading.evidence.document.definition import (  # noqa: E501
    ReadingEvidenceDocument,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.inventory.definition import (  # noqa: E501
    ReadingEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.source.request import (
    ReadingEvidenceSourceRequest,
)


@dataclass(frozen=True, slots=True)
class ReadingEvidenceSourceResult(AbstractDataObjectActionResult):
    """Bind verified provider evidence to one canonical document source."""

    request: ReadingEvidenceSourceRequest
    document: ReadingEvidenceDocument
    inventory: ReadingEvidenceInventory
    projection_result_id: ReadingEvidenceIdentity
    provider_implementation_id: str
    provider_verification_id: str
    result_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.request) is not ReadingEvidenceSourceRequest:
            raise TypeError("request has an unsupported type")
        if type(self.document) is not ReadingEvidenceDocument:
            raise TypeError("document has an unsupported type")
        if type(self.inventory) is not ReadingEvidenceInventory:
            raise TypeError("inventory has an unsupported type")
        if (
            type(self.projection_result_id) is not ReadingEvidenceIdentity
            or self.projection_result_id.kind
            is not ReadingEvidenceIdentityKind.PROJECTION_RESULT
        ):
            raise TypeError("projection_result_id has the wrong identity role")
        if (
            self.document.document_id != self.request.document_id
            or self.inventory.inventory_id != self.request.inventory_id
            or self.projection_result_id != self.request.projection_result_id
        ):
            raise ValueError("source result differs from requested identities")
        measures = self.inventory.measures
        if (
            measures.page_count > self.request.maximum_page_count
            or measures.block_count > self.request.maximum_block_count
            or measures.artifact_count > self.request.maximum_artifact_count
        ):
            raise ValueError("source result exceeds requested evidence bounds")
        for value, name in (
            (self.provider_implementation_id, "provider_implementation_id"),
            (self.provider_verification_id, "provider_verification_id"),
        ):
            if type(value) is not str or not value:
                raise ValueError(f"{name} must be non-empty")
            if len(value.encode("utf-8", errors="strict")) > 512:
                raise ValueError(f"{name} exceeds its limit")
        object.__setattr__(
            self,
            "result_id",
            stable_id(
                "reading-evidence-source-result",
                self.request.request_id,
                self.document.document_id.value,
                self.inventory.inventory_id.value,
                self.projection_result_id.value,
                self.provider_implementation_id,
                self.provider_verification_id,
            ),
        )
