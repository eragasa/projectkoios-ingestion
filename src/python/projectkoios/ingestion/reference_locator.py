"""Bounded page locators over exact ingestion-owned transcript evidence."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.reference_evidence import (
    ReferenceEvidenceRecord,
    ReferenceEvidenceVerificationError,
)
from projectkoios.ingestion.transcript_projection import (
    CleanTranscriptArtifact,
    CleanTranscriptPage,
)

REFERENCE_LOCATOR_CONTRACT_VERSION = "0.1.0"
REFERENCE_LOCATOR_PROCESSOR_NAME = "projectkoios-reference-page-locator"
REFERENCE_LOCATOR_PROCESSOR_VERSION = "1"
REFERENCE_LOCATOR_MAX_ANCHORS = 32
REFERENCE_LOCATOR_MAX_ANCHOR_CHARACTERS = 256
REFERENCE_LOCATOR_MAX_ANCHOR_TOKENS = 32
REFERENCE_LOCATOR_MAX_PAGE_CHARACTERS = 2_000_000
_ANCHOR_ID = re.compile(r"reference-topic-anchor:sha256:[0-9a-f]{64}")
_IDENTITY_PATTERNS = {
    "locator_id": re.compile(r"reference-page-locator:sha256:[0-9a-f]{64}"),
    "reference_evidence_record_id": re.compile(
        r"reference-evidence-record:sha256:[0-9a-f]{64}"
    ),
    "transcript_artifact_id": re.compile(
        r"clean-transcript-artifact:sha256:[0-9a-f]{64}"
    ),
    "page_id": re.compile(r"clean-transcript-page:sha256:[0-9a-f]{64}"),
}
_LIMITATIONS = (
    "automated_unreviewed",
    "not_claim_support",
    "not_human_proofread",
    "not_publication_suitable",
    "not_scientifically_validated",
    "page_navigation_only",
)


class ReferenceLocatorError(ValueError):
    """Base failure for bounded reference-page location."""


class ReferenceLocatorLimitError(ReferenceLocatorError):
    """Raised before locator processing exceeds a hard bound."""


class ReferenceLocatorVerificationError(ReferenceLocatorError):
    """Raised when supplied evidence does not form one exact lineage."""


class ReferencePageLocatorStatus(StrEnum):
    """Mechanical whole-token phrase-match status."""

    MATCH = "match"
    NO_MATCH = "no_match"


def _tokens(value: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    tokens: list[str] = []
    current: list[str] = []
    for character in normalized:
        if character.isalnum():
            current.append(character)
        elif current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return tuple(tokens)


def reference_topic_anchor_identity(value: str) -> str:
    """Return the payload-free identity of one bounded topic anchor."""
    if type(value) is not str:
        raise TypeError("topic anchor must be a built-in string")
    if not value or value.strip() != value:
        raise ValueError("topic anchor must be nonempty and trimmed")
    if len(value) > REFERENCE_LOCATOR_MAX_ANCHOR_CHARACTERS:
        raise ReferenceLocatorLimitError("topic anchor exceeds text limit")
    tokens = _tokens(value)
    if not tokens:
        raise ValueError("topic anchor must contain alphanumeric tokens")
    if len(tokens) > REFERENCE_LOCATOR_MAX_ANCHOR_TOKENS:
        raise ReferenceLocatorLimitError("topic anchor exceeds token limit")
    return stable_id(
        "reference-topic-anchor",
        tokens,
        REFERENCE_LOCATOR_CONTRACT_VERSION,
    )


def _anchor_inventory(values: object) -> tuple[str, ...]:
    if type(values) is not tuple:
        raise TypeError("topic_anchor_alternatives must be a built-in tuple")
    if not values:
        raise ValueError("topic_anchor_alternatives must not be empty")
    if len(values) > REFERENCE_LOCATOR_MAX_ANCHORS:
        raise ReferenceLocatorLimitError("topic anchor count exceeds limit")
    normalized: set[tuple[str, ...]] = set()
    for value in values:
        if type(value) is not str:
            raise TypeError("topic anchors must be built-in strings")
        reference_topic_anchor_identity(value)
        tokens = _tokens(value)
        if tokens in normalized:
            raise ValueError("normalized topic anchors must be unique")
        normalized.add(tokens)
    if values != tuple(sorted(values)) or len(set(values)) != len(values):
        raise ValueError("topic anchors must be sorted and unique")
    return values


def _verified_page(
    record: ReferenceEvidenceRecord,
    transcript: CleanTranscriptArtifact,
    *,
    page_id: str,
    page_index: int,
) -> CleanTranscriptPage:
    if type(record) is not ReferenceEvidenceRecord:
        raise TypeError("record must be ReferenceEvidenceRecord")
    if type(transcript) is not CleanTranscriptArtifact:
        raise TypeError("transcript must be CleanTranscriptArtifact")
    try:
        record.require_reusable()
    except ReferenceEvidenceVerificationError as error:
        raise ReferenceLocatorVerificationError(
            "reference evidence is not reusable"
        ) from error
    if (
        record.transcript.artifact_id != transcript.artifact_id
        or record.transcript.structured_transcription_result_id
        != transcript.transcription_result_id
        or record.transcript.layout_result_ids != transcript.layout_result_ids
        or record.transcript.text_sha256 != transcript.text_sha256
        or record.transcript.text_utf8_byte_length
        != transcript.utf8_byte_length
        or record.extraction.document_id != transcript.document_id
        or record.source.blob_id != transcript.source_blob_id
        or record.source.content_sha256 != transcript.source_content_hash
    ):
        raise ReferenceLocatorVerificationError(
            "transcript does not match reference-evidence lineage"
        )
    matches = tuple(
        page
        for page in transcript.pages
        if page.page_id == page_id and page.page_index == page_index
    )
    if len(matches) != 1:
        raise ReferenceLocatorVerificationError(
            "locator page does not identify one transcript page"
        )
    page = matches[0]
    if len(page.text) > REFERENCE_LOCATOR_MAX_PAGE_CHARACTERS:
        raise ReferenceLocatorLimitError("transcript page exceeds text limit")
    return page


@dataclass(frozen=True, slots=True)
class ReferencePageLocator:
    """Identify one exact transcript page and bounded topic alternatives."""

    locator_id: str
    reference_evidence_record_id: str
    transcript_artifact_id: str
    page_id: str
    page_index: int
    topic_anchor_alternatives: tuple[str, ...]
    contract_version: str = REFERENCE_LOCATOR_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        record: ReferenceEvidenceRecord,
        transcript: CleanTranscriptArtifact,
        page_index: int,
        topic_anchor_alternatives: tuple[str, ...],
    ) -> ReferencePageLocator:
        """Create a locator only after exact lineage and page verification."""
        if type(page_index) is not int or page_index < 0:
            raise ValueError("page_index must be a nonnegative built-in int")
        matches = tuple(
            page for page in transcript.pages if page.page_index == page_index
        )
        if len(matches) != 1:
            raise ReferenceLocatorVerificationError(
                "page_index does not identify one transcript page"
            )
        page = _verified_page(
            record,
            transcript,
            page_id=matches[0].page_id,
            page_index=page_index,
        )
        anchors = _anchor_inventory(topic_anchor_alternatives)
        locator_id = stable_id(
            "reference-page-locator",
            record.record_id,
            transcript.artifact_id,
            page.page_id,
            page.page_index,
            anchors,
            REFERENCE_LOCATOR_CONTRACT_VERSION,
        )
        return cls(
            locator_id,
            record.record_id,
            transcript.artifact_id,
            page.page_id,
            page.page_index,
            anchors,
        )

    def __post_init__(self) -> None:
        if self.contract_version != REFERENCE_LOCATOR_CONTRACT_VERSION:
            raise ValueError("unsupported reference locator contract")
        for name, value in (
            ("locator_id", self.locator_id),
            ("reference_evidence_record_id", self.reference_evidence_record_id),
            ("transcript_artifact_id", self.transcript_artifact_id),
            ("page_id", self.page_id),
        ):
            if (
                type(value) is not str
                or _IDENTITY_PATTERNS[name].fullmatch(value) is None
            ):
                raise ValueError(f"{name} has an invalid identity grammar")
        if type(self.page_index) is not int or self.page_index < 0:
            raise ValueError("page_index must be a nonnegative built-in int")
        anchors = _anchor_inventory(self.topic_anchor_alternatives)
        expected = stable_id(
            "reference-page-locator",
            self.reference_evidence_record_id,
            self.transcript_artifact_id,
            self.page_id,
            self.page_index,
            anchors,
            self.contract_version,
        )
        if self.locator_id != expected:
            raise ValueError("reference page locator identity is inconsistent")


@dataclass(frozen=True, slots=True)
class ReferencePageLocatorResult:
    """Payload-free page-location result requiring later manual review."""

    result_id: str
    locator_id: str
    reference_evidence_record_id: str
    transcript_artifact_id: str
    page_id: str
    page_index: int
    topic_anchor_identities: tuple[str, ...]
    page_text_sha256: str
    page_text_utf8_byte_length: int
    matched_topic_anchor_identities: tuple[str, ...]
    unmatched_topic_anchor_identities: tuple[str, ...]
    status: ReferencePageLocatorStatus
    limitations: tuple[str, ...] = _LIMITATIONS
    processor_name: str = REFERENCE_LOCATOR_PROCESSOR_NAME
    processor_version: str = REFERENCE_LOCATOR_PROCESSOR_VERSION
    contract_version: str = REFERENCE_LOCATOR_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name, value in (
            ("locator_id", self.locator_id),
            ("reference_evidence_record_id", self.reference_evidence_record_id),
            ("transcript_artifact_id", self.transcript_artifact_id),
            ("page_id", self.page_id),
        ):
            if (
                type(value) is not str
                or _IDENTITY_PATTERNS[name].fullmatch(value) is None
            ):
                raise ValueError(f"{name} has an invalid identity grammar")
        if type(self.page_index) is not int or self.page_index < 0:
            raise ValueError("page_index must be a nonnegative built-in int")
        if (
            type(self.page_text_sha256) is not str
            or len(self.page_text_sha256) != 64
            or any(
                value not in "0123456789abcdef"
                for value in self.page_text_sha256
            )
        ):
            raise ValueError("page_text_sha256 must be 64 lowercase hex")
        if (
            type(self.page_text_utf8_byte_length) is not int
            or self.page_text_utf8_byte_length < 0
            or self.page_text_utf8_byte_length
            > REFERENCE_LOCATOR_MAX_PAGE_CHARACTERS * 4
        ):
            raise ValueError("page text byte length is outside its bound")
        for name, values in (
            ("topic_anchor_identities", self.topic_anchor_identities),
            (
                "matched_topic_anchor_identities",
                self.matched_topic_anchor_identities,
            ),
            (
                "unmatched_topic_anchor_identities",
                self.unmatched_topic_anchor_identities,
            ),
        ):
            if (
                type(values) is not tuple
                or values != tuple(sorted(values))
                or len(values) != len(set(values))
                or any(
                    type(value) is not str
                    or _ANCHOR_ID.fullmatch(value) is None
                    for value in values
                )
            ):
                raise ValueError(
                    f"{name} must contain sorted anchor identities"
                )
        if not self.topic_anchor_identities:
            raise ValueError(
                "topic anchor identity inventory must not be empty"
            )
        if len(self.topic_anchor_identities) > REFERENCE_LOCATOR_MAX_ANCHORS:
            raise ReferenceLocatorLimitError(
                "topic anchor identity count exceeds limit"
            )
        if set(self.matched_topic_anchor_identities) & set(
            self.unmatched_topic_anchor_identities
        ):
            raise ValueError("matched and unmatched anchors must be disjoint")
        if (
            tuple(
                sorted(
                    self.matched_topic_anchor_identities
                    + self.unmatched_topic_anchor_identities
                )
            )
            != self.topic_anchor_identities
        ):
            raise ValueError("result must partition topic anchor identities")
        if type(self.status) is not ReferencePageLocatorStatus:
            raise TypeError("status must be ReferencePageLocatorStatus")
        expected_status = (
            ReferencePageLocatorStatus.MATCH
            if self.matched_topic_anchor_identities
            else ReferencePageLocatorStatus.NO_MATCH
        )
        if self.status is not expected_status:
            raise ValueError("status does not match the anchor partition")
        if self.limitations != _LIMITATIONS:
            raise ValueError("reference locator limitations are incomplete")
        if self.processor_name != REFERENCE_LOCATOR_PROCESSOR_NAME:
            raise ValueError("unsupported reference locator processor")
        if self.processor_version != REFERENCE_LOCATOR_PROCESSOR_VERSION:
            raise ValueError("unsupported reference locator processor version")
        if self.contract_version != REFERENCE_LOCATOR_CONTRACT_VERSION:
            raise ValueError("unsupported reference locator contract")
        expected = stable_id(
            "reference-page-locator-result",
            self.locator_id,
            self.reference_evidence_record_id,
            self.transcript_artifact_id,
            self.page_id,
            self.page_index,
            self.topic_anchor_identities,
            self.page_text_sha256,
            self.page_text_utf8_byte_length,
            self.matched_topic_anchor_identities,
            self.unmatched_topic_anchor_identities,
            self.status,
            self.limitations,
            self.processor_name,
            self.processor_version,
            self.contract_version,
        )
        if self.result_id != expected:
            raise ValueError(
                "reference page locator result identity is inconsistent"
            )


class ReferencePageLocatorChecker:
    """Check complete token phrases over one exact clean-transcript page."""

    __slots__ = ()

    def execute(
        self,
        *,
        record: ReferenceEvidenceRecord,
        transcript: CleanTranscriptArtifact,
        locator: ReferencePageLocator,
    ) -> ReferencePageLocatorResult:
        """Return payload-free mechanical navigation evidence."""
        if type(locator) is not ReferencePageLocator:
            raise TypeError("locator must be ReferencePageLocator")
        page = _verified_page(
            record,
            transcript,
            page_id=locator.page_id,
            page_index=locator.page_index,
        )
        if (
            locator.reference_evidence_record_id != record.record_id
            or locator.transcript_artifact_id != transcript.artifact_id
        ):
            raise ReferenceLocatorVerificationError(
                "locator does not match supplied evidence"
            )
        page_tokens = _tokens(page.text)
        matched = tuple(
            anchor
            for anchor in locator.topic_anchor_alternatives
            if self._contains(page_tokens, _tokens(anchor))
        )
        unmatched = tuple(
            anchor
            for anchor in locator.topic_anchor_alternatives
            if anchor not in matched
        )
        anchor_identities = {
            anchor: reference_topic_anchor_identity(anchor)
            for anchor in locator.topic_anchor_alternatives
        }
        all_identities = tuple(sorted(anchor_identities.values()))
        matched_identities = tuple(
            sorted(anchor_identities[anchor] for anchor in matched)
        )
        unmatched_identities = tuple(
            sorted(anchor_identities[anchor] for anchor in unmatched)
        )
        encoded = page.text.encode("utf-8")
        digest = hashlib.sha256(encoded).hexdigest()
        status = (
            ReferencePageLocatorStatus.MATCH
            if matched
            else ReferencePageLocatorStatus.NO_MATCH
        )
        result_id = stable_id(
            "reference-page-locator-result",
            locator.locator_id,
            locator.reference_evidence_record_id,
            locator.transcript_artifact_id,
            locator.page_id,
            locator.page_index,
            all_identities,
            digest,
            len(encoded),
            matched_identities,
            unmatched_identities,
            status,
            _LIMITATIONS,
            REFERENCE_LOCATOR_PROCESSOR_NAME,
            REFERENCE_LOCATOR_PROCESSOR_VERSION,
            REFERENCE_LOCATOR_CONTRACT_VERSION,
        )
        return ReferencePageLocatorResult(
            result_id,
            locator.locator_id,
            locator.reference_evidence_record_id,
            locator.transcript_artifact_id,
            locator.page_id,
            locator.page_index,
            all_identities,
            digest,
            len(encoded),
            matched_identities,
            unmatched_identities,
            status,
        )

    @staticmethod
    def _contains(haystack: tuple[str, ...], needle: tuple[str, ...]) -> bool:
        if not needle or len(needle) > len(haystack):
            return False
        return any(
            haystack[index : index + len(needle)] == needle
            for index in range(len(haystack) - len(needle) + 1)
        )
