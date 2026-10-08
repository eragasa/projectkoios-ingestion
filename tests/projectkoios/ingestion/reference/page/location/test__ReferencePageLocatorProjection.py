"""Verification for bounded reference page-locator projection."""

from dataclasses import replace

import pytest
from projectkoios.ingestion.reference.page.location.anchor import (
    ReferenceMatchTokenSequence,
    ReferenceTopicAnchor,
)
from projectkoios.ingestion.reference.page.location.identity import (
    ReferencePageLocatorIdentityDerivation,
)
from projectkoios.ingestion.reference.page.location.limits.definition import (
    REFERENCE_LOCATOR_MAX_ANCHORS,
    REFERENCE_LOCATOR_MAX_PAGE_CHARACTERS,
)
from projectkoios.ingestion.reference.page.location.limits.error import (
    ReferenceLocatorLimitError,
)
from projectkoios.ingestion.reference.page.location.projection.actionizer import (  # noqa: E501
    ReferencePageLocatorProjectionActionizer,
)
from projectkoios.ingestion.reference.page.location.projection.request import (
    ReferencePageLocatorProjectionRequest,
)

from tests.projectkoios.ingestion.reference.page.location.fixture import (
    ReferencePageLocationFixture,
)


def test__reference_page_locator_projection__preserves_identity(
    reference_page_location_fixture: ReferencePageLocationFixture,
) -> None:
    record, transcript = reference_page_location_fixture.evidence()

    locator = ReferencePageLocatorProjectionActionizer().action(
        request=ReferencePageLocatorProjectionRequest(
            record=record,
            transcript=transcript,
            page_index=0,
            topic_anchor_alternatives=(
                reference_page_location_fixture.anchors("effective mass")
            ),
        )
    )

    assert locator.locator_id == (
        "reference-page-locator:sha256:"
        "fb47bda158077e80623c23278018966354472e6165144b75f81880aaa74d34ea"
    )
    assert locator.reference_evidence_record_id == record.record_id
    assert locator.transcript_result_id == transcript.result_id
    assert locator.page_id == transcript.pages[0].page_id


def test__reference_page_locator_projection__requires_typed_request() -> None:
    with pytest.raises(
        TypeError,
        match="request must be ReferencePageLocatorProjectionRequest",
    ):
        ReferencePageLocatorProjectionActionizer().action(
            request=object()  # type: ignore[arg-type]
        )


def test__locator_projection__requires_semantic_anchor_inventory(
    reference_page_location_fixture: ReferencePageLocationFixture,
) -> None:
    record, transcript = reference_page_location_fixture.evidence()

    with pytest.raises(
        TypeError,
        match="topic anchors must be ReferenceTopicAnchorInventory",
    ):
        ReferencePageLocatorProjectionRequest(
            record=record,
            transcript=transcript,
            page_index=0,
            topic_anchor_alternatives=("effective mass",),  # type: ignore[arg-type]
        )


def test__locator_projection__bounds_every_tokenization_entry() -> None:
    with pytest.raises(ReferenceLocatorLimitError, match="text limit"):
        ReferenceMatchTokenSequence(
            "x" * (REFERENCE_LOCATOR_MAX_PAGE_CHARACTERS + 1)
        )
    with pytest.raises(ValueError, match="valid UTF-8"):
        ReferenceTopicAnchor("\ud800")


def test__locator_projection__validates_before_identity_hashing(
    reference_page_location_fixture: ReferencePageLocationFixture,
) -> None:
    record, transcript = reference_page_location_fixture.evidence()
    anchors = reference_page_location_fixture.anchors("effective mass")

    with pytest.raises(ValueError, match="identity grammar"):
        ReferencePageLocatorIdentityDerivation(
            reference_evidence_record_id="unbounded-external-value",
            transcript_result_id=transcript.result_id,
            page_id=transcript.pages[0].page_id,
            page_index=0,
            topic_anchors=anchors,
            contract_version="0.1.0",
        )


def test__locator_projection__rejects_normalization_collision(
    reference_page_location_fixture: ReferencePageLocationFixture,
) -> None:
    record, transcript = reference_page_location_fixture.evidence()

    with pytest.raises(ValueError, match="normalized topic anchors"):
        ReferencePageLocatorProjectionRequest(
            record=record,
            transcript=transcript,
            page_index=0,
            topic_anchor_alternatives=reference_page_location_fixture.anchors(
                "effective mass",
                "effective-mass",
            ),
        )


def test__reference_page_locator_projection__rejects_tampering_and_excess(
    reference_page_location_fixture: ReferencePageLocationFixture,
) -> None:
    record, transcript = reference_page_location_fixture.evidence()
    locator = ReferencePageLocatorProjectionActionizer().action(
        request=ReferencePageLocatorProjectionRequest(
            record=record,
            transcript=transcript,
            page_index=0,
            topic_anchor_alternatives=(
                reference_page_location_fixture.anchors("effective mass")
            ),
        )
    )

    with pytest.raises(ValueError, match="identity is inconsistent"):
        replace(
            locator,
            locator_id=f"reference-page-locator:sha256:{'0' * 64}",
        )
    with pytest.raises(ReferenceLocatorLimitError, match="count"):
        ReferencePageLocatorProjectionRequest(
            record=record,
            transcript=transcript,
            page_index=0,
            topic_anchor_alternatives=reference_page_location_fixture.anchors(
                *(
                    f"anchor {index:02d}"
                    for index in range(REFERENCE_LOCATOR_MAX_ANCHORS + 1)
                )
            ),
        )
