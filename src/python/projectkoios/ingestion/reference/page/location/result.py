"""Immutable payload-free reference page-location action result."""

from dataclasses import dataclass

from projectkoios.ingestion.base.actionizer.result import (
    AbstractDataObjectActionResult,
)
from projectkoios.ingestion.reference.page.location.definition import (
    REFERENCE_LOCATOR_CONTRACT_VERSION,
    REFERENCE_LOCATOR_PROCESSOR_NAME,
    REFERENCE_LOCATOR_PROCESSOR_VERSION,
)
from projectkoios.ingestion.reference.page.location.identity import (
    ReferencePageLocatorResultIdentityDerivation,
)
from projectkoios.ingestion.reference.page.location.inventory import (
    ReferenceTopicAnchorIdentityInventory,
)
from projectkoios.ingestion.reference.page.location.limitation import (
    ReferencePageLocationLimitations,
)
from projectkoios.ingestion.reference.page.location.status import (
    ReferencePageLocatorStatus,
)

REFERENCE_PAGE_LOCATION_LIMITATIONS = ReferencePageLocationLimitations()


@dataclass(frozen=True, slots=True)
class ReferencePageLocatorResult(AbstractDataObjectActionResult):
    """Payload-free page-location result requiring later manual review."""

    result_id: str
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
    limitations: ReferencePageLocationLimitations = (
        REFERENCE_PAGE_LOCATION_LIMITATIONS
    )
    processor_name: str = REFERENCE_LOCATOR_PROCESSOR_NAME
    processor_version: str = REFERENCE_LOCATOR_PROCESSOR_VERSION
    contract_version: str = REFERENCE_LOCATOR_CONTRACT_VERSION

    def __post_init__(self) -> None:
        expected = ReferencePageLocatorResultIdentityDerivation(
            locator_id=self.locator_id,
            reference_evidence_record_id=self.reference_evidence_record_id,
            transcript_result_id=self.transcript_result_id,
            page_id=self.page_id,
            page_index=self.page_index,
            topic_anchor_identities=self.topic_anchor_identities,
            page_text_sha256=self.page_text_sha256,
            page_text_utf8_byte_length=self.page_text_utf8_byte_length,
            matched_topic_anchor_identities=(
                self.matched_topic_anchor_identities
            ),
            unmatched_topic_anchor_identities=(
                self.unmatched_topic_anchor_identities
            ),
            status=self.status,
            limitations=self.limitations,
            processor_name=self.processor_name,
            processor_version=self.processor_version,
            contract_version=self.contract_version,
        ).value
        if self.result_id != expected:
            raise ValueError(
                "reference page locator result identity is inconsistent"
            )
