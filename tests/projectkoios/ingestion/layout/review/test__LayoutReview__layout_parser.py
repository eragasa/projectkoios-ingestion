from __future__ import annotations

from dataclasses import replace

import pytest
from projectkoios.ingestion.integrations.layout_parser.actionizer import (
    LayoutParserRegionProposalActionizer,
)
from projectkoios.ingestion.integrations.layout_parser.configuration import (
    LayoutParserProposalConfiguration,
)
from projectkoios.ingestion.integrations.layout_parser.detection import (
    LayoutParserDetection,
)
from projectkoios.ingestion.integrations.layout_parser.limits import (
    definition as layout_parser_limits,
)
from projectkoios.ingestion.integrations.layout_parser.limits.error import (
    LayoutParserLimitError,
)
from projectkoios.ingestion.integrations.layout_parser.request import (
    LayoutParserProposalRequest,
)
from projectkoios.ingestion.layout.limits.definition import (
    MAX_LAYOUT_COORDINATE_MAGNITUDE,
)
from projectkoios.ingestion.layout.limits.error import LayoutLimitError
from projectkoios.ingestion.layout.proposal.kind import LayoutRegionKind
from projectkoios.ingestion.serialization import serialize_contract
from projectkoios.ingestion.sha256.hash import SHA256Hash

from tests.projectkoios.ingestion.layout.review.layout_review_support import (
    LayoutReviewFixture,
)

FIXTURE = LayoutReviewFixture()

MAX_LAYOUT_PARSER_DETECTION_LABEL_CHARACTERS = (
    layout_parser_limits.MAX_LAYOUT_PARSER_DETECTION_LABEL_CHARACTERS
)
MAX_LAYOUT_PARSER_LABEL_CHARACTERS = (
    layout_parser_limits.MAX_LAYOUT_PARSER_LABEL_CHARACTERS
)
MAX_LAYOUT_PARSER_LABEL_MAPPING_CHARACTERS = (
    layout_parser_limits.MAX_LAYOUT_PARSER_LABEL_MAPPING_CHARACTERS
)


def test__layout_parser_adapter__retains_lineage_without_vendor_import() -> (
    None
):
    _, adapter_result, _, _ = FIXTURE.prepared_case()

    assert adapter_result.proposal_source.detector_name == "layoutparser:effdet"
    assert adapter_result.proposal_source.resource_sha256 == "b" * 64
    assert len(adapter_result.proposals) == 1
    assert adapter_result.proposals[0].kind is LayoutRegionKind.TEXT
    assert serialize_contract(adapter_result) == serialize_contract(
        LayoutParserRegionProposalActionizer().action(
            request=adapter_result.request
        )
    )
    assert len(adapter_result.adaptations) == 1
    assert (
        adapter_result.adaptations[0].detection_id
        == adapter_result.request.detections[0].detection_id
    )


def test__layout_parser_request__rejects_unmapped_label() -> None:
    _, _, render = FIXTURE.render_evidence()
    detection = LayoutParserDetection.create(
        render_id=render.render_id,
        label="Equation",
        bounding_box_pixels=(20.0, 20.0, 80.0, 40.0),
        confidence=0.95,
    )

    with pytest.raises(ValueError, match="not mapped"):
        LayoutParserProposalRequest.create(
            render=render,
            detections=(detection,),
            configuration=FIXTURE.layout_parser_configuration(),
        )


def test__layout_parser_result__rejects_cross_request_relabeling() -> None:
    _, _, render = FIXTURE.render_evidence()
    configuration = FIXTURE.layout_parser_configuration()
    detections = (
        LayoutParserDetection.create(
            render_id=render.render_id,
            label="Text",
            bounding_box_pixels=(20.0, 20.0, 80.0, 40.0),
            confidence=0.95,
        ),
        LayoutParserDetection.create(
            render_id=render.render_id,
            label="Table",
            bounding_box_pixels=(20.0, 80.0, 80.0, 120.0),
            confidence=0.85,
        ),
    )
    request = LayoutParserProposalRequest.create(
        render=render,
        detections=detections,
        configuration=configuration,
    )
    result = LayoutParserRegionProposalActionizer().action(request=request)
    reordered_request = LayoutParserProposalRequest.create(
        render=render,
        detections=tuple(reversed(detections)),
        configuration=configuration,
    )

    assert tuple(
        adaptation.detection_id for adaptation in result.adaptations
    ) == tuple(detection.detection_id for detection in detections)
    with pytest.raises(ValueError, match="proposals differ"):
        replace(result, request=reordered_request)
    with pytest.raises(ValueError, match="adaptation IDs must be unique"):
        replace(
            result,
            adaptations=(result.adaptations[0], result.adaptations[0]),
        )
    with pytest.raises(ValueError, match="proposals differ"):
        replace(result, adaptations=tuple(reversed(result.adaptations)))

    substituted_detection = LayoutParserDetection.create(
        render_id=render.render_id,
        label="Figure",
        bounding_box_pixels=(100.0, 100.0, 140.0, 140.0),
        confidence=0.75,
    )
    substituted_result = LayoutParserRegionProposalActionizer().action(
        request=LayoutParserProposalRequest.create(
            render=render,
            detections=(substituted_detection,),
            configuration=configuration,
        )
    )
    with pytest.raises(ValueError, match="proposals differ"):
        replace(
            result,
            adaptations=(
                substituted_result.adaptations[0],
                result.adaptations[1],
            ),
        )


@pytest.mark.parametrize(
    ("label_length", "bounding_box_pixels", "expected_error"),
    (
        # Exact label length and ordinary geometry are accepted together.
        (
            MAX_LAYOUT_PARSER_LABEL_CHARACTERS,
            (1.0, 1.0, 2.0, 2.0),
            None,
        ),
        # One extra label character fails before detection identity hashing.
        (
            MAX_LAYOUT_PARSER_LABEL_CHARACTERS + 1,
            (1.0, 1.0, 2.0, 2.0),
            LayoutParserLimitError,
        ),
        # The exact coordinate-magnitude boundary remains representable.
        (
            1,
            (0.0, 0.0, MAX_LAYOUT_COORDINATE_MAGNITUDE, 1.0),
            None,
        ),
        # One unit beyond the coordinate bound fails before identity hashing.
        (
            1,
            (0.0, 0.0, MAX_LAYOUT_COORDINATE_MAGNITUDE + 1.0, 1.0),
            LayoutLimitError,
        ),
        # A zero-area model box is never valid detection geometry.
        (1, (1.0, 1.0, 1.0, 2.0), ValueError),
    ),
)
def test__layout_parser_detection__bounds_values_before_identity(
    label_length: int,
    bounding_box_pixels: tuple[float, float, float, float],
    expected_error: type[Exception] | None,
) -> None:
    _, _, render = FIXTURE.render_evidence()
    label = "x" * label_length
    if expected_error is None:
        detection = LayoutParserDetection.create(
            render_id=render.render_id,
            label=label,
            bounding_box_pixels=bounding_box_pixels,
            confidence=1.0,
        )
        assert detection.bounding_box_pixels == bounding_box_pixels
    else:
        with pytest.raises(expected_error):
            LayoutParserDetection.create(
                render_id=render.render_id,
                label=label,
                bounding_box_pixels=bounding_box_pixels,
                confidence=1.0,
            )


@pytest.mark.parametrize(
    ("mapping_count", "accepted"),
    (
        # Sixty-four maximum-length labels exactly fill the aggregate bound.
        (
            MAX_LAYOUT_PARSER_LABEL_MAPPING_CHARACTERS
            // MAX_LAYOUT_PARSER_LABEL_CHARACTERS,
            True,
        ),
        # One more maximum-length label exceeds the aggregate bound.
        (
            MAX_LAYOUT_PARSER_LABEL_MAPPING_CHARACTERS
            // MAX_LAYOUT_PARSER_LABEL_CHARACTERS
            + 1,
            False,
        ),
    ),
)
def test__layout_parser_configuration__bounds_aggregate_label_text(
    mapping_count: int,
    accepted: bool,
) -> None:
    label_mapping = tuple(
        (
            f"{index:03d}"
            + "x" * (MAX_LAYOUT_PARSER_LABEL_CHARACTERS - 3),
            LayoutRegionKind.TEXT,
        )
        for index in range(mapping_count)
    )
    if accepted:
        configuration = LayoutParserProposalConfiguration(
            package_version="0.3.4",
            backend_name="effdet",
            backend_version="0.4.1",
            model_identity="fixture:model",
            model_sha256=SHA256Hash("d" * 64),
            label_mapping=label_mapping,
        )
        assert len(configuration.label_mapping) == mapping_count
    else:
        with pytest.raises(LayoutParserLimitError):
            LayoutParserProposalConfiguration(
                package_version="0.3.4",
                backend_name="effdet",
                backend_version="0.4.1",
                model_identity="fixture:model",
                model_sha256=SHA256Hash("d" * 64),
                label_mapping=label_mapping,
            )


@pytest.mark.parametrize(
    ("detection_count", "accepted"),
    (
        # Repeated labels exactly fill the request aggregate-text bound.
        (
            MAX_LAYOUT_PARSER_DETECTION_LABEL_CHARACTERS
            // MAX_LAYOUT_PARSER_LABEL_CHARACTERS,
            True,
        ),
        # One further bounded detection exceeds aggregate request text.
        (
            MAX_LAYOUT_PARSER_DETECTION_LABEL_CHARACTERS
            // MAX_LAYOUT_PARSER_LABEL_CHARACTERS
            + 1,
            False,
        ),
    ),
)
def test__layout_parser_request__bounds_aggregate_detection_labels(
    detection_count: int,
    accepted: bool,
) -> None:
    _, _, render = FIXTURE.render_evidence()
    label = "x" * MAX_LAYOUT_PARSER_LABEL_CHARACTERS
    configuration = LayoutParserProposalConfiguration(
        package_version="0.3.4",
        backend_name="effdet",
        backend_version="0.4.1",
        model_identity="fixture:model",
        model_sha256=SHA256Hash("e" * 64),
        label_mapping=((label, LayoutRegionKind.TEXT),),
    )
    detections = tuple(
        LayoutParserDetection.create(
            render_id=render.render_id,
            label=label,
            bounding_box_pixels=(
                float(index % 100),
                float(index // 100),
                float(index % 100) + 0.5,
                float(index // 100) + 0.5,
            ),
            confidence=1.0,
        )
        for index in range(detection_count)
    )
    if accepted:
        request = LayoutParserProposalRequest.create(
            render=render,
            detections=detections,
            configuration=configuration,
        )
        assert len(request.detections) == detection_count
    else:
        with pytest.raises(LayoutParserLimitError):
            LayoutParserProposalRequest.create(
                render=render,
                detections=detections,
                configuration=configuration,
            )


def test__layout_parser_contracts__reject_stale_identities() -> None:
    _, adapter_result, _, _ = FIXTURE.prepared_case()

    with pytest.raises(ValueError, match="proposals differ"):
        replace(adapter_result, adaptations=())
    with pytest.raises(ValueError, match="inconsistent"):
        replace(
            adapter_result.proposals[0],
            proposal_id="layout-region-proposal:sha256:" + "0" * 64,
        )
