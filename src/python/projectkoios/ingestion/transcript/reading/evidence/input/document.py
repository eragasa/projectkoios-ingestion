"""Exact reading document producer evidence."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.artifact.managed.media.type import (
    ManagedArtifactMediaType,
)
from projectkoios.ingestion.artifact.managed.reference import (
    ManagedArtifactReference,
)
from projectkoios.ingestion.sha256.hash import SHA256Hash
from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.derivation import (  # noqa: E501
    ReadingEvidenceIdentityDerivation,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)


@dataclass(frozen=True, slots=True)
class ReadingDocumentProducerEvidence:
    """Bind source/document lineage without constructing canonical pages."""

    document_id: ReadingEvidenceIdentity
    source_id: ReadingEvidenceIdentity
    source_artifact: ManagedArtifactReference
    title: str
    expected_page_count: int
    extraction_result_id: ReadingEvidenceIdentity
    producer_id: ReadingEvidenceIdentity
    producer_version: str
    record_id: ReadingEvidenceIdentity = field(init=False)

    def __post_init__(self) -> None:
        expected_roles = (
            (
                self.document_id,
                ReadingEvidenceIdentityKind.DOCUMENT,
                "document_id",
            ),
            (self.source_id, ReadingEvidenceIdentityKind.SOURCE, "source_id"),
            (
                self.extraction_result_id,
                ReadingEvidenceIdentityKind.EXTRACTION_RESULT,
                "extraction_result_id",
            ),
            (
                self.producer_id,
                ReadingEvidenceIdentityKind.PRODUCER,
                "producer_id",
            ),
        )
        for value, kind, name in expected_roles:
            if (
                type(value) is not ReadingEvidenceIdentity
                or value.kind is not kind
            ):
                raise TypeError(f"{name} has the wrong identity role")
        if type(self.source_artifact) is not ManagedArtifactReference:
            raise TypeError("source_artifact must be ManagedArtifactReference")
        if (
            self.source_artifact.media_type
            is not ManagedArtifactMediaType.APPLICATION_PDF
        ):
            raise ReadingEvidenceError("reading source artifact must be a PDF")
        READING_EVIDENCE_LIMITS.require_text(
            self.title,
            "title",
            maximum_bytes=READING_EVIDENCE_LIMITS.maximum_title_bytes,
        )
        pages = READING_EVIDENCE_LIMITS.require_positive_int(
            self.expected_page_count, "expected_page_count"
        )
        if pages > READING_EVIDENCE_LIMITS.maximum_pages:
            raise ReadingEvidenceError(
                "expected_page_count exceeds the page limit"
            )
        READING_EVIDENCE_LIMITS.require_text(
            self.producer_version,
            "producer_version",
            maximum_bytes=(
                READING_EVIDENCE_LIMITS.maximum_producer_version_bytes
            ),
        )
        object.__setattr__(
            self,
            "record_id",
            ReadingEvidenceIdentityDerivation.derive(
                kind=ReadingEvidenceIdentityKind.DOCUMENT_PRODUCER,
                prefix="reading-document-producer",
                material={
                    "document_id": self.document_id.value,
                    "source_id": self.source_id.value,
                    "source_artifact_id": self.source_artifact.artifact_id,
                    "title": self.title,
                    "expected_page_count": pages,
                    "extraction_result_id": self.extraction_result_id.value,
                    "producer_id": self.producer_id.value,
                    "producer_version": self.producer_version,
                },
            ),
        )

    @property
    def source_sha256(self) -> SHA256Hash:
        """Return the canonical digest bound by the source artifact."""
        return self.source_artifact.sha256
