"""Exact native and OCR reading text streams."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
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
from projectkoios.ingestion.transcript.reading.evidence.page.location import (
    ReadingPageLocation,
)
from projectkoios.ingestion.transcript.reading.evidence.status.review import (
    ReadingReviewStatus,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.kind import (
    ReadingTextStreamKind,
)


@dataclass(frozen=True, slots=True)
class ReadingTextStreamEvidence:
    """Retain one exact bounded page text stream and producer lineage."""

    kind: ReadingTextStreamKind
    page_location: ReadingPageLocation
    text: str
    upstream_id: ReadingEvidenceIdentity
    producer_id: ReadingEvidenceIdentity
    composition_id: ReadingEvidenceIdentity | None
    automated: bool
    accepted: bool
    review_status: ReadingReviewStatus
    text_sha256: SHA256Hash = field(init=False)
    utf8_byte_length: int = field(init=False)
    stream_id: ReadingEvidenceIdentity = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ReadingTextStreamKind):
            raise TypeError("kind must be ReadingTextStreamKind")
        if type(self.page_location) is not ReadingPageLocation:
            raise TypeError("page_location must be ReadingPageLocation")
        text = READING_EVIDENCE_LIMITS.require_string(
            self.text,
            "stream text",
            maximum_bytes=READING_EVIDENCE_LIMITS.maximum_page_text_bytes,
        )
        upstream_kind = (
            ReadingEvidenceIdentityKind.EXTRACTION_RESULT
            if self.kind is ReadingTextStreamKind.NATIVE
            else ReadingEvidenceIdentityKind.OCR_RESULT
        )
        if type(self.upstream_id) is not ReadingEvidenceIdentity or (
            self.upstream_id.kind is not upstream_kind
        ):
            raise TypeError("upstream_id has the wrong stream-source role")
        if type(self.producer_id) is not ReadingEvidenceIdentity or (
            self.producer_id.kind is not ReadingEvidenceIdentityKind.PRODUCER
        ):
            raise TypeError("producer_id must be a producer identity")
        if self.kind is ReadingTextStreamKind.NATIVE:
            if self.composition_id is not None:
                raise ReadingEvidenceError(
                    "native stream cannot have a composition"
                )
        elif type(self.composition_id) is not ReadingEvidenceIdentity or (
            self.composition_id.kind
            is not ReadingEvidenceIdentityKind.COMPOSITION
        ):
            raise TypeError("OCR stream requires a composition identity")
        if type(self.automated) is not bool or type(self.accepted) is not bool:
            raise TypeError(
                "stream automated and accepted states must be booleans"
            )
        if not isinstance(self.review_status, ReadingReviewStatus):
            raise TypeError("review_status must be ReadingReviewStatus")
        if self.accepted is not (
            self.review_status is ReadingReviewStatus.ACCEPTED
        ):
            raise ReadingEvidenceError(
                "stream accepted state conflicts with review status"
            )
        content = text.encode("utf-8", errors="strict")
        digest = SHA256Fingerprinter.fingerprint(content=content)
        object.__setattr__(self, "text_sha256", digest)
        object.__setattr__(self, "utf8_byte_length", len(content))
        object.__setattr__(
            self,
            "stream_id",
            ReadingEvidenceIdentityDerivation.derive(
                kind=ReadingEvidenceIdentityKind.TEXT_STREAM,
                prefix="reading-text-stream",
                material={
                    "kind": self.kind,
                    "page_location_id": self.page_location.location_id.value,
                    "text_sha256": digest,
                    "utf8_byte_length": len(content),
                    "upstream_id": self.upstream_id.value,
                    "producer_id": self.producer_id.value,
                    "composition_id": (
                        None
                        if self.composition_id is None
                        else self.composition_id.value
                    ),
                    "automated": self.automated,
                    "accepted": self.accepted,
                    "review_status": self.review_status,
                },
            ),
        )
