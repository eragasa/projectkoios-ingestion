"""Verification for bounded mechanical reference page matching."""

import pytest
from projectkoios.ingestion.reference.page.location.anchor import (
    ReferenceTopicAnchor,
)
from projectkoios.ingestion.reference.page.location.error import (
    ReferenceLocatorVerificationError,
)
from projectkoios.ingestion.reference.page.location.matching.actionizer import (
    ReferencePageLocationActionizer,
)
from projectkoios.ingestion.reference.page.location.matching.request import (
    ReferencePageLocationRequest,
)
from projectkoios.ingestion.reference.page.location.projection.actionizer import (  # noqa: E501
    ReferencePageLocatorProjectionActionizer,
)
from projectkoios.ingestion.reference.page.location.projection.request import (
    ReferencePageLocatorProjectionRequest,
)
from projectkoios.ingestion.reference.page.location.status import (
    ReferencePageLocatorStatus,
)

from tests.projectkoios.ingestion.reference.page.location.fixture import (
    ReferencePageLocationFixture,
)


def test__reference_page_location__matches_complete_unicode_phrases(
    reference_page_location_fixture: ReferencePageLocationFixture,
) -> None:
    record, transcript = reference_page_location_fixture.evidence()
    locator = ReferencePageLocatorProjectionActionizer().action(
        request=ReferencePageLocatorProjectionRequest(
            record=record,
            transcript=transcript,
            page_index=0,
            topic_anchor_alternatives=reference_page_location_fixture.anchors(
                "effective mass",
                "β decay",
            ),
        )
    )

    result = ReferencePageLocationActionizer().action(
        request=ReferencePageLocationRequest(
            record=record,
            transcript=transcript,
            locator=locator,
        )
    )

    assert result.status is ReferencePageLocatorStatus.MATCH
    assert tuple(result.matched_topic_anchor_identities) == tuple(
        sorted(
            (
                ReferenceTopicAnchor("effective mass").anchor_id,
                ReferenceTopicAnchor("β decay").anchor_id,
            )
        )
    )
    assert not result.unmatched_topic_anchor_identities
    assert result.page_text_sha256 == transcript.pages[0].text_sha256
    assert "effective mass" not in repr(result)
    assert "β decay" not in repr(result)
    assert not any(
        field in result.__dataclass_fields__
        for field in (
            "locator",
            "text",
            "topic_anchor_alternatives",
            "source_path",
            "quotation",
        )
    )


def test__reference_page_location__preserves_historical_result_identity(
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

    result = ReferencePageLocationActionizer().action(
        request=ReferencePageLocationRequest(
            record=record,
            transcript=transcript,
            locator=locator,
        )
    )

    assert result.result_id == (
        "reference-page-locator-result:sha256:"
        "89fa0b08ce9aad0afd53c62573571b6250916bcb283f3c0e3621d40a443e92b3"
    )


def test__reference_page_location__does_not_match_token_substrings(
    reference_page_location_fixture: ReferencePageLocationFixture,
) -> None:
    record, transcript = reference_page_location_fixture.evidence(
        page_text="A biomass model is discussed."
    )
    locator = ReferencePageLocatorProjectionActionizer().action(
        request=ReferencePageLocatorProjectionRequest(
            record=record,
            transcript=transcript,
            page_index=0,
            topic_anchor_alternatives=reference_page_location_fixture.anchors(
                "mass"
            ),
        )
    )

    result = ReferencePageLocationActionizer().action(
        request=ReferencePageLocationRequest(
            record=record,
            transcript=transcript,
            locator=locator,
        )
    )

    assert result.status is ReferencePageLocatorStatus.NO_MATCH
    assert not result.matched_topic_anchor_identities
    assert tuple(result.unmatched_topic_anchor_identities) == (
        ReferenceTopicAnchor("mass").anchor_id,
    )


def test__reference_page_location__requires_typed_request() -> None:
    with pytest.raises(
        TypeError,
        match="request must be ReferencePageLocationRequest",
    ):
        ReferencePageLocationActionizer().action(
            request=object()  # type: ignore[arg-type]
        )


def test__reference_page_location__rejects_cross_source_locator(
    reference_page_location_fixture: ReferencePageLocationFixture,
) -> None:
    record, transcript = reference_page_location_fixture.evidence()
    other_record, other_transcript = reference_page_location_fixture.evidence(
        source_digest="b" * 64
    )
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

    with pytest.raises(
        ReferenceLocatorVerificationError,
        match="evidence",
    ):
        ReferencePageLocationActionizer().action(
            request=ReferencePageLocationRequest(
                record=other_record,
                transcript=other_transcript,
                locator=locator,
            )
        )
