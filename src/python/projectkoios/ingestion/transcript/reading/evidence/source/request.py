"""Backend-neutral bounded canonical reading-evidence source requests."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)


@dataclass(frozen=True, slots=True)
class ReadingEvidenceSourceRequest(DataObjectActionRequest):
    """Select one exact canonical source under explicit evidence bounds."""

    provider_source_id: str
    document_id: ReadingEvidenceIdentity
    projection_result_id: ReadingEvidenceIdentity
    inventory_id: ReadingEvidenceIdentity
    maximum_page_count: int
    maximum_block_count: int
    maximum_artifact_count: int
    maximum_provider_record_count: int
    authority_id: str
    request_id: str = field(init=False)

    def __post_init__(self) -> None:
        for value, name, maximum in (
            (self.provider_source_id, "provider_source_id", 512),
            (self.authority_id, "authority_id", 512),
        ):
            if type(value) is not str or not value:
                raise ValueError(f"{name} must be non-empty")
            if len(value.encode("utf-8", errors="strict")) > maximum:
                raise ValueError(f"{name} exceeds its limit")
        for identity, kind, name in (
            (
                self.document_id,
                ReadingEvidenceIdentityKind.EVIDENCE_DOCUMENT,
                "document_id",
            ),
            (
                self.projection_result_id,
                ReadingEvidenceIdentityKind.PROJECTION_RESULT,
                "projection_result_id",
            ),
            (
                self.inventory_id,
                ReadingEvidenceIdentityKind.EVIDENCE_INVENTORY,
                "inventory_id",
            ),
        ):
            if (
                type(identity) is not ReadingEvidenceIdentity
                or identity.kind is not kind
            ):
                raise TypeError(f"{name} has the wrong identity role")
        bounds = (
            (
                self.maximum_page_count,
                READING_EVIDENCE_LIMITS.maximum_pages,
                "maximum_page_count",
            ),
            (
                self.maximum_block_count,
                READING_EVIDENCE_LIMITS.maximum_blocks,
                "maximum_block_count",
            ),
            (
                self.maximum_artifact_count,
                READING_EVIDENCE_LIMITS.maximum_references,
                "maximum_artifact_count",
            ),
            (
                self.maximum_provider_record_count,
                READING_EVIDENCE_LIMITS.maximum_records,
                "maximum_provider_record_count",
            ),
        )
        for bound_value, maximum, bound_name in bounds:
            if type(bound_value) is not int or not 1 <= bound_value <= maximum:
                raise ValueError(f"{bound_name} is invalid")
        object.__setattr__(
            self,
            "request_id",
            stable_id(
                "reading-evidence-source-request",
                self.provider_source_id,
                self.document_id.value,
                self.projection_result_id.value,
                self.inventory_id.value,
                tuple(value for value, _, _ in bounds),
                self.authority_id,
            ),
        )
