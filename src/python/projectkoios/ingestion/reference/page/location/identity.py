"""Bounded deterministic reference page-location identity derivations."""

import re
from dataclasses import dataclass

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.reference.page.location.definition import (
    REFERENCE_LOCATOR_CONTRACT_VERSION,
    REFERENCE_LOCATOR_PROCESSOR_NAME,
    REFERENCE_LOCATOR_PROCESSOR_VERSION,
)
from projectkoios.ingestion.reference.page.location.inventory import (
    ReferenceTopicAnchorIdentityInventory,
    ReferenceTopicAnchorInventory,
    ReferenceTopicAnchorMatch,
)
from projectkoios.ingestion.reference.page.location.limitation import (
    ReferencePageLocationLimitations,
)
from projectkoios.ingestion.reference.page.location.limits.definition import (
    REFERENCE_LOCATOR_MAX_PAGE_CHARACTERS,
)
from projectkoios.ingestion.reference.page.location.status import (
    ReferencePageLocatorStatus,
)
from projectkoios.ingestion.sha256.hash import SHA256Hash

_REFERENCE_EVIDENCE_RECORD_ID_PATTERN = re.compile(
    r"reference-evidence-record:sha256:[0-9a-f]{64}"
)
_TRANSCRIPT_RESULT_ID_PATTERN = re.compile(
    r"clean-transcript-result:sha256:[0-9a-f]{64}"
)
_PAGE_ID_PATTERN = re.compile(r"clean-transcript-page:sha256:[0-9a-f]{64}")
_LOCATOR_ID_PATTERN = re.compile(r"reference-page-locator:sha256:[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class ReferencePageLocatorIdentityDerivation:
    """Validated ordered input to one stable locator identity."""

    reference_evidence_record_id: str
    transcript_result_id: str
    page_id: str
    page_index: int
    topic_anchors: ReferenceTopicAnchorInventory
    contract_version: str

    def __post_init__(self) -> None:
        for name, value, pattern in (
            (
                "reference_evidence_record_id",
                self.reference_evidence_record_id,
                _REFERENCE_EVIDENCE_RECORD_ID_PATTERN,
            ),
            (
                "transcript_result_id",
                self.transcript_result_id,
                _TRANSCRIPT_RESULT_ID_PATTERN,
            ),
            ("page_id", self.page_id, _PAGE_ID_PATTERN),
        ):
            if type(value) is not str or pattern.fullmatch(value) is None:
                raise ValueError(f"{name} has an invalid identity grammar")
        if type(self.page_index) is not int or self.page_index < 0:
            raise ValueError("page_index must be a nonnegative built-in int")
        if type(self.topic_anchors) is not ReferenceTopicAnchorInventory:
            raise TypeError(
                "topic_anchors must be ReferenceTopicAnchorInventory"
            )
        if self.contract_version != REFERENCE_LOCATOR_CONTRACT_VERSION:
            raise ValueError("unsupported reference locator contract")

    @property
    def value(self) -> str:
        """Return the stable locator identifier from validated values."""
        return stable_id(
            "reference-page-locator",
            self.reference_evidence_record_id,
            self.transcript_result_id,
            self.page_id,
            self.page_index,
            tuple(anchor.text for anchor in self.topic_anchors),
            self.contract_version,
        )


@dataclass(frozen=True, slots=True)
class ReferencePageLocatorResultIdentityDerivation:
    """Validated ordered input to one stable page-location result identity."""

    locator_id: str
    reference_evidence_record_id: str
    transcript_result_id: str
    page_id: str
    page_index: int
    topic_anchor_identities: ReferenceTopicAnchorIdentityInventory
    page_text_sha256: str
    page_text_utf8_byte_length: int
    matched_topic_anchor_identities: ReferenceTopicAnchorIdentityInventory
    unmatched_topic_anchor_identities: ReferenceTopicAnchorIdentityInventory
    status: ReferencePageLocatorStatus
    limitations: ReferencePageLocationLimitations
    processor_name: str
    processor_version: str
    contract_version: str

    def __post_init__(self) -> None:
        for name, value, pattern in (
            ("locator_id", self.locator_id, _LOCATOR_ID_PATTERN),
            (
                "reference_evidence_record_id",
                self.reference_evidence_record_id,
                _REFERENCE_EVIDENCE_RECORD_ID_PATTERN,
            ),
            (
                "transcript_result_id",
                self.transcript_result_id,
                _TRANSCRIPT_RESULT_ID_PATTERN,
            ),
            ("page_id", self.page_id, _PAGE_ID_PATTERN),
        ):
            if type(value) is not str or pattern.fullmatch(value) is None:
                raise ValueError(f"{name} has an invalid identity grammar")
        if type(self.page_index) is not int or self.page_index < 0:
            raise ValueError("page_index must be a nonnegative built-in int")
        ReferenceTopicAnchorMatch(
            all_identities=self.topic_anchor_identities,
            matched_identities=self.matched_topic_anchor_identities,
            unmatched_identities=self.unmatched_topic_anchor_identities,
        )
        if not SHA256Hash.is_canonical(self.page_text_sha256):
            raise ValueError("page_text_sha256 must be 64 lowercase hex")
        if (
            type(self.page_text_utf8_byte_length) is not int
            or self.page_text_utf8_byte_length < 0
            or self.page_text_utf8_byte_length
            > REFERENCE_LOCATOR_MAX_PAGE_CHARACTERS * 4
        ):
            raise ValueError("page text byte length is outside its bound")
        if type(self.status) is not ReferencePageLocatorStatus:
            raise TypeError("status must be ReferencePageLocatorStatus")
        expected_status = (
            ReferencePageLocatorStatus.MATCH
            if self.matched_topic_anchor_identities
            else ReferencePageLocatorStatus.NO_MATCH
        )
        if self.status is not expected_status:
            raise ValueError("status does not match the anchor partition")
        if type(self.limitations) is not ReferencePageLocationLimitations:
            raise TypeError(
                "limitations must be ReferencePageLocationLimitations"
            )
        if self.processor_name != REFERENCE_LOCATOR_PROCESSOR_NAME:
            raise ValueError("unsupported reference locator processor")
        if self.processor_version != REFERENCE_LOCATOR_PROCESSOR_VERSION:
            raise ValueError("unsupported reference locator processor version")
        if self.contract_version != REFERENCE_LOCATOR_CONTRACT_VERSION:
            raise ValueError("unsupported reference locator contract")

    @property
    def value(self) -> str:
        """Return the stable result identifier from validated values."""
        return stable_id(
            "reference-page-locator-result",
            self.locator_id,
            self.reference_evidence_record_id,
            self.transcript_result_id,
            self.page_id,
            self.page_index,
            tuple(self.topic_anchor_identities),
            self.page_text_sha256,
            self.page_text_utf8_byte_length,
            tuple(self.matched_topic_anchor_identities),
            tuple(self.unmatched_topic_anchor_identities),
            self.status,
            tuple(item.value for item in self.limitations),
            self.processor_name,
            self.processor_version,
            self.contract_version,
        )
