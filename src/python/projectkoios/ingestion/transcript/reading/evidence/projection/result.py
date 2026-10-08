"""Immutable results from pure canonical reading projection."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.base.actionizer.result import (
    AbstractDataObjectActionResult,
)
from projectkoios.ingestion.transcript.reading.evidence.document.definition import (  # noqa: E501
    ReadingEvidenceDocument,
)
from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
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
from projectkoios.ingestion.transcript.reading.evidence.limitation.inventory import (  # noqa: E501
    ReadingEvidenceLimitationInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.identity import (  # noqa: E501
    ReadingEvidenceProjectionIdentityDerivation,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.request import (  # noqa: E501
    ReadingEvidenceProjectionRequest,
)
from projectkoios.ingestion.transcript.reading.evidence.reconciliation.definition import (  # noqa: E501
    ReadingEvidenceReconciliation,
)


@dataclass(frozen=True, slots=True)
class ReadingEvidenceProjectionResult(AbstractDataObjectActionResult):
    """Bind one exact request to a reconciled canonical reading document."""

    request: ReadingEvidenceProjectionRequest
    document: ReadingEvidenceDocument
    inventory: ReadingEvidenceInventory
    reconciliation: ReadingEvidenceReconciliation
    processor_id: ReadingEvidenceIdentity
    processor_version: str
    limitations: ReadingEvidenceLimitationInventory
    result_id: ReadingEvidenceIdentity = field(init=False)

    def __post_init__(self) -> None:
        if type(self.request) is not ReadingEvidenceProjectionRequest:
            raise TypeError("request must be ReadingEvidenceProjectionRequest")
        if type(self.document) is not ReadingEvidenceDocument:
            raise TypeError("document must be ReadingEvidenceDocument")
        if type(self.inventory) is not ReadingEvidenceInventory:
            raise TypeError("inventory must be ReadingEvidenceInventory")
        if type(self.reconciliation) is not ReadingEvidenceReconciliation:
            raise TypeError(
                "reconciliation must be ReadingEvidenceReconciliation"
            )
        if (
            self.reconciliation.observed != self.inventory
            or not self.reconciliation.complete
        ):
            raise ReadingEvidenceError("projection inventory is not reconciled")
        if (
            type(self.processor_id) is not ReadingEvidenceIdentity
            or self.processor_id.kind
            is not ReadingEvidenceIdentityKind.PRODUCER
        ):
            raise TypeError("processor_id has the wrong identity role")
        READING_EVIDENCE_LIMITS.require_text(
            self.processor_version,
            "processor_version",
            maximum_bytes=READING_EVIDENCE_LIMITS.maximum_producer_version_bytes,
        )
        if type(self.limitations) is not ReadingEvidenceLimitationInventory:
            raise TypeError("limitations has an unsupported type")
        if self.limitations != self.document.limitations:
            raise ReadingEvidenceError(
                "result limitations differ from document"
            )
        object.__setattr__(
            self,
            "result_id",
            ReadingEvidenceProjectionIdentityDerivation.derive_result(
                request_id=self.request.request_id,
                document_id=self.document.document_id,
                inventory_id=self.inventory.inventory_id,
                reconciliation_id=self.reconciliation.reconciliation_id,
                processor_id=self.processor_id,
                processor_version=self.processor_version,
            ),
        )
