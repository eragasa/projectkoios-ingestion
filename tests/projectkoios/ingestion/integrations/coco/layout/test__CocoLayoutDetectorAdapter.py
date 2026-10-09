"""Framework-neutral local detector observation adapter tests."""

import pytest
from projectkoios.ingestion.integrations.coco.layout.detector.actionizer import (  # noqa: E501
    CocoLayoutDetectorObservationActionizer,
)
from projectkoios.ingestion.integrations.coco.layout.detector.adaptation import (  # noqa: E501
    CocoLayoutDetectorAdaptationInventory,
)
from projectkoios.ingestion.integrations.coco.layout.detector.label import (
    CocoLayoutDetectorLabelDisposition,
    CocoLayoutDetectorLabelMappingInventory,
)
from projectkoios.ingestion.integrations.coco.layout.detector.limitation import (  # noqa: E501
    CocoLayoutDetectorLimitationCode,
)
from projectkoios.ingestion.integrations.coco.layout.detector.observation import (  # noqa: E501
    CocoLayoutDetectorObservation,
    CocoLayoutDetectorObservationInventory,
)
from projectkoios.ingestion.integrations.coco.layout.detector.request import (
    CocoLayoutDetectorRequest,
)
from projectkoios.ingestion.integrations.coco.layout.detector.result import (
    CocoLayoutDetectorResult,
)

from tests.projectkoios.ingestion.integrations.coco.layout.detector_fixture import (  # noqa: E501
    coco_layout_detector_request,
)


@pytest.mark.parametrize(
    ("model_label_id", "expected_label", "expected_category"),
    tuple(
        (index, label, index + 1 if index < 11 else None)
        for index, label in enumerate(
            (
                "caption",
                "footnote",
                "formula",
                "list_item",
                "page_footer",
                "page_header",
                "picture",
                "section_header",
                "table",
                "text",
                "title",
                "document_index",
                "code",
                "checkbox_selected",
                "checkbox_unselected",
                "form",
                "key_value_region",
            )
        )
    ),
)
def test_docling_heron_label_registry_is_explicit(
    model_label_id: int,
    expected_label: str,
    expected_category: int | None,
) -> None:
    mapping = (
        CocoLayoutDetectorLabelMappingInventory.docling_heron_v0_1().require(
            model_label_id
        )
    )

    assert mapping.model_label == expected_label
    assert mapping.category_id == expected_category
    assert mapping.disposition is (
        CocoLayoutDetectorLabelDisposition.ACCEPTED
        if expected_category is not None
        else CocoLayoutDetectorLabelDisposition.UNSUPPORTED
    )


@pytest.mark.parametrize("model_label_id", (-1, True, 17))
def test_detector_label_registry_rejects_invalid_id(
    model_label_id: int,
) -> None:
    mappings = CocoLayoutDetectorLabelMappingInventory.docling_heron_v0_1()

    with pytest.raises(ValueError, match="label ID is absent"):
        mappings.require(model_label_id)


def test_detector_adapter_assigns_canonical_ids_and_explicit_limitations() -> (
    None
):
    request = coco_layout_detector_request()
    result = CocoLayoutDetectorObservationActionizer().action(request=request)

    assert tuple(
        (item.annotation_id, item.category_id, item.bbox_xywh_pixels)
        for item in result.detections
    ) == (
        (1, 3, (20.0, 20.0, 60.0, 20.0)),
        (2, 10, (20.0, 80.0, 60.0, 20.0)),
    )
    assert tuple(item.code for item in result.limitations) == (
        CocoLayoutDetectorLimitationCode.UNSUPPORTED_LABEL,
        CocoLayoutDetectorLimitationCode.BELOW_CONFIDENCE_THRESHOLD,
    )
    assert len(result.adaptations) + len(result.limitations) == len(
        request.observations
    )


def test_detector_adapter_canonical_detections_ignore_producer_order() -> None:
    forward = CocoLayoutDetectorObservationActionizer().action(
        request=coco_layout_detector_request()
    )
    reverse = CocoLayoutDetectorObservationActionizer().action(
        request=coco_layout_detector_request(reverse=True)
    )

    assert forward.detections == reverse.detections
    assert forward.request.request_id != reverse.request.request_id
    assert forward.result_id != reverse.result_id


def test_detector_result_rejects_forged_adaptations() -> None:
    result = CocoLayoutDetectorObservationActionizer().action(
        request=coco_layout_detector_request()
    )

    with pytest.raises(ValueError, match="differs from deterministic"):
        CocoLayoutDetectorResult(
            request=result.request,
            adaptations=CocoLayoutDetectorAdaptationInventory(),
            limitations=result.limitations,
            actionizer_name=result.actionizer_name,
            actionizer_version=result.actionizer_version,
        )


def test_detector_request_rejects_out_of_bounds_observation() -> None:
    request = coco_layout_detector_request()
    invalid = CocoLayoutDetectorObservation(
        render_id=request.render.render_id,
        model_label_id=9,
        bounding_box_xyxy_pixels=(0.0, 0.0, 201.0, 1.0),
        confidence=0.9,
    )

    with pytest.raises(ValueError, match="exceeds image bounds"):
        CocoLayoutDetectorRequest(
            render=request.render,
            image=request.image,
            observations=CocoLayoutDetectorObservationInventory(invalid),
            configuration=request.configuration,
        )
