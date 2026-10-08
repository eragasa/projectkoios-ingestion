"""Immutable bounded reference page-locator action result."""

from dataclasses import dataclass

from projectkoios.ingestion.base.actionizer.result import (
    AbstractDataObjectActionResult,
)
from projectkoios.ingestion.reference.page.location.definition import (
    REFERENCE_LOCATOR_CONTRACT_VERSION,
)
from projectkoios.ingestion.reference.page.location.identity import (
    ReferencePageLocatorIdentityDerivation,
)
from projectkoios.ingestion.reference.page.location.inventory import (
    ReferenceTopicAnchorInventory,
)


@dataclass(frozen=True, slots=True)
class ReferencePageLocator(AbstractDataObjectActionResult):
    """Identify one exact transcript page and bounded topic alternatives."""

    locator_id: str
    reference_evidence_record_id: str
    transcript_result_id: str
    page_id: str
    page_index: int
    topic_anchor_alternatives: ReferenceTopicAnchorInventory
    contract_version: str = REFERENCE_LOCATOR_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != REFERENCE_LOCATOR_CONTRACT_VERSION:
            raise ValueError("unsupported reference locator contract")
        if (
            type(self.topic_anchor_alternatives)
            is not ReferenceTopicAnchorInventory
        ):
            raise TypeError(
                "topic anchors must be ReferenceTopicAnchorInventory"
            )
        expected = ReferencePageLocatorIdentityDerivation(
            reference_evidence_record_id=self.reference_evidence_record_id,
            transcript_result_id=self.transcript_result_id,
            page_id=self.page_id,
            page_index=self.page_index,
            topic_anchors=self.topic_anchor_alternatives,
            contract_version=self.contract_version,
        ).value
        if self.locator_id != expected:
            raise ValueError("reference page locator identity is inconsistent")
