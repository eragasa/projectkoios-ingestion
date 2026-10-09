from __future__ import annotations

import pytest
from projectkoios.ingestion.integrations.docling.layout.reading.actionizer import (  # noqa: E501
    DoclingReadingOrderActionizer,
)
from projectkoios.ingestion.integrations.docling.layout.reading.configuration import (  # noqa: E501
    DoclingReadingOrderConfiguration,
)
from projectkoios.ingestion.integrations.docling.layout.reading.kind import (
    DoclingReadingOrderFailureKind,
    DoclingReadingOrderStatus,
)
from projectkoios.ingestion.integrations.docling.layout.reading.limits import (
    MAX_DOCLING_READING_ORDER_ELEMENTS,
)
from projectkoios.ingestion.integrations.docling.layout.reading.provider import (  # noqa: E501
    DoclingReadingOrderProvider,
    InstalledDoclingReadingOrderProvider,
)
from projectkoios.ingestion.integrations.docling.layout.reading.request import (
    DoclingReadingOrderRequest,
)
from projectkoios.ingestion.integrations.docling.layout.reading.result import (
    DoclingReadingOrderResult,
)
from projectkoios.ingestion.layout.proposal.kind import LayoutRegionKind
from projectkoios.ingestion.layout.reading.order.candidate import (
    LayoutReadingOrderCandidateElement,
    LayoutReadingOrderCandidateElementInventory,
)
from projectkoios.ingestion.layout.reading.order.kind import (
    LayoutReadingDirection,
)


class StubDoclingReadingOrderProvider(DoclingReadingOrderProvider):
    def __init__(self, *, output: object, implementation_id: str) -> None:
        self.output = output
        self._implementation_id = implementation_id

    @property
    def implementation_id(self) -> str:
        return self._implementation_id

    def order(self, *, request: DoclingReadingOrderRequest) -> object:
        del request
        return self.output


def reading_order_request(
    *,
    entries: tuple[
        tuple[
            str,
            LayoutRegionKind,
            tuple[float, float, float, float],
        ],
        ...,
    ],
    direction: LayoutReadingDirection = (LayoutReadingDirection.LEFT_TO_RIGHT),
) -> DoclingReadingOrderRequest:
    configuration = DoclingReadingOrderConfiguration()
    return DoclingReadingOrderRequest(
        render_id="render:sha256:test",
        upstream_evidence_id="layout-evidence:sha256:test",
        page_width_pixels=100,
        page_height_pixels=100,
        direction=direction,
        elements=LayoutReadingOrderCandidateElementInventory(
            *(
                LayoutReadingOrderCandidateElement(
                    region_id=element_id,
                    source_index=index,
                    kind=kind,
                    bounding_box_pixels=box,
                )
                for index, (element_id, kind, box) in enumerate(entries)
            )
        ),
        configuration=configuration,
    )


def two_column_entries(
    *, row_major: bool
) -> tuple[
    tuple[str, LayoutRegionKind, tuple[float, float, float, float]], ...
]:
    left_top = ("left-top", LayoutRegionKind.TEXT, (5.0, 10.0, 45.0, 20.0))
    left_bottom = (
        "left-bottom",
        LayoutRegionKind.TEXT,
        (5.0, 30.0, 45.0, 40.0),
    )
    right_top = (
        "right-top",
        LayoutRegionKind.TEXT,
        (55.0, 10.0, 95.0, 20.0),
    )
    right_bottom = (
        "right-bottom",
        LayoutRegionKind.TEXT,
        (55.0, 30.0, 95.0, 40.0),
    )
    if row_major:
        return left_top, right_top, left_bottom, right_bottom
    return left_top, left_bottom, right_top, right_bottom


def test_installed_docling_provider_produces_complete_candidate() -> None:
    request = reading_order_request(entries=two_column_entries(row_major=False))

    result = DoclingReadingOrderActionizer(
        provider=InstalledDoclingReadingOrderProvider()
    ).action(request=request)

    assert result.status is DoclingReadingOrderStatus.CANDIDATE_PRODUCED
    assert result.candidate_evidence is not None
    assert tuple(result.candidate_evidence.candidate) == (
        "left-top",
        "left-bottom",
        "right-top",
        "right-bottom",
    )
    assert result.failure_kind is None
    assert result.requires_verification is True


@pytest.mark.benchmark
def test_docling_candidate_retains_source_order_influence() -> None:
    provider = InstalledDoclingReadingOrderProvider()
    actionizer = DoclingReadingOrderActionizer(provider=provider)

    column_major = actionizer.action(
        request=reading_order_request(
            entries=two_column_entries(row_major=False)
        )
    )
    row_major = actionizer.action(
        request=reading_order_request(
            entries=two_column_entries(row_major=True)
        )
    )

    assert column_major.candidate_evidence is not None
    assert tuple(column_major.candidate_evidence.candidate) == (
        "left-top",
        "left-bottom",
        "right-top",
        "right-bottom",
    )
    assert row_major.candidate_evidence is not None
    assert tuple(row_major.candidate_evidence.candidate) == (
        "left-top",
        "right-top",
        "left-bottom",
        "right-bottom",
    )
    assert column_major.result_id == (
        "docling-reading-order-result:sha256:"
        "f4c095553771ee4d0b01d7954d74324d171183b47c3f0f08aa8d02c70b44a22c"
    )
    assert row_major.result_id == (
        "docling-reading-order-result:sha256:"
        "673106057ba744330a5b0a8af92fcbfe33d252e30be602d5c856b410c1daaabe"
    )


@pytest.mark.parametrize(
    ("output", "expected_failure"),
    (
        (
            ["left-top", "left-bottom", "right-top", "right-bottom"],
            DoclingReadingOrderFailureKind.OUTPUT_TYPE_INVALID,
        ),
        (
            tuple(
                "element" for _ in range(MAX_DOCLING_READING_ORDER_ELEMENTS + 1)
            ),
            DoclingReadingOrderFailureKind.OUTPUT_ELEMENT_LIMIT_EXCEEDED,
        ),
        (
            ("left-top", "left-top", "right-top", "right-bottom"),
            DoclingReadingOrderFailureKind.OUTPUT_DUPLICATE_ELEMENT,
        ),
        (
            ("left-top", "left-bottom", "right-top", "unknown"),
            DoclingReadingOrderFailureKind.OUTPUT_UNKNOWN_ELEMENT,
        ),
        (
            ("left-top", "left-bottom", "right-top"),
            DoclingReadingOrderFailureKind.OUTPUT_INCOMPLETE,
        ),
    ),
)
def test_actionizer_rejects_invalid_provider_output(
    output: object,
    expected_failure: DoclingReadingOrderFailureKind,
) -> None:
    request = reading_order_request(entries=two_column_entries(row_major=False))
    provider = StubDoclingReadingOrderProvider(
        output=output,
        implementation_id=(request.configuration.provider_implementation_id),
    )

    result = DoclingReadingOrderActionizer(provider=provider).action(
        request=request
    )

    assert result.status is DoclingReadingOrderStatus.UNRESOLVED
    assert result.candidate_evidence is None
    assert result.failure_kind is expected_failure


def test_result_rejects_forged_successful_provider_identity() -> None:
    request = reading_order_request(entries=two_column_entries(row_major=False))
    exact = DoclingReadingOrderActionizer(
        provider=InstalledDoclingReadingOrderProvider()
    ).action(request=request)
    assert exact.candidate_evidence is not None

    with pytest.raises(ValueError, match="differs from configuration"):
        DoclingReadingOrderResult(
            request=request,
            provider_implementation_id="provider:drifted",
            status=DoclingReadingOrderStatus.CANDIDATE_PRODUCED,
            candidate_evidence=exact.candidate_evidence,
            failure_kind=None,
        )


def test_result_rejects_untyped_provider_identity_mismatch() -> None:
    request = reading_order_request(entries=two_column_entries(row_major=False))

    with pytest.raises(ValueError, match="version-mismatch evidence"):
        DoclingReadingOrderResult(
            request=request,
            provider_implementation_id="provider:drifted",
            status=DoclingReadingOrderStatus.UNRESOLVED,
            candidate_evidence=None,
            failure_kind=DoclingReadingOrderFailureKind.PROVIDER_FAILURE,
        )


def test_installed_provider_rejects_right_to_left_direction() -> None:
    request = reading_order_request(
        entries=two_column_entries(row_major=False),
        direction=LayoutReadingDirection.RIGHT_TO_LEFT,
    )

    result = DoclingReadingOrderActionizer(
        provider=InstalledDoclingReadingOrderProvider()
    ).action(request=request)

    assert result.status is DoclingReadingOrderStatus.UNRESOLVED
    assert (
        result.failure_kind
        is DoclingReadingOrderFailureKind.UNSUPPORTED_DIRECTION
    )


def test_installed_provider_rejects_unsupported_region_kind() -> None:
    request = reading_order_request(
        entries=(("sidebar", LayoutRegionKind.SIDEBAR, (5.0, 5.0, 40.0, 40.0)),)
    )

    result = DoclingReadingOrderActionizer(
        provider=InstalledDoclingReadingOrderProvider()
    ).action(request=request)

    assert result.status is DoclingReadingOrderStatus.UNRESOLVED
    assert (
        result.failure_kind
        is DoclingReadingOrderFailureKind.UNSUPPORTED_REGION_KIND
    )


def test_element_inventory_requires_contiguous_source_order() -> None:
    with pytest.raises(
        ValueError,
        match="contiguous",
    ):
        LayoutReadingOrderCandidateElementInventory(
            LayoutReadingOrderCandidateElement(
                region_id="element",
                source_index=1,
                kind=LayoutRegionKind.TEXT,
                bounding_box_pixels=(1.0, 1.0, 2.0, 2.0),
            )
        )
