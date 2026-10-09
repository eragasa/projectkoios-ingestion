"""COCO-compatible layout proposal adaptation tests."""

from __future__ import annotations

from dataclasses import replace

import pytest
from projectkoios.ingestion.integrations.coco.layout.actionizer import (
    CocoLayoutRegionProposalActionizer,
)
from projectkoios.ingestion.integrations.coco.layout.category import (
    CocoLayoutCategory,
    CocoLayoutCategoryInventory,
)
from projectkoios.ingestion.integrations.coco.layout.configuration import (
    CocoLayoutProposalConfiguration,
)
from projectkoios.ingestion.integrations.coco.layout.detection import (
    CocoLayoutDetection,
    CocoLayoutDetectionInventory,
)
from projectkoios.ingestion.integrations.coco.layout.image import (
    CocoLayoutImage,
)
from projectkoios.ingestion.integrations.coco.layout.profile import (
    CocoLayoutProfile,
)
from projectkoios.ingestion.integrations.coco.layout.request import (
    CocoLayoutProposalRequest,
)
from projectkoios.ingestion.layout.proposal.kind import LayoutRegionKind
from projectkoios.ingestion.sha256.hash import SHA256Hash

from tests.projectkoios.ingestion.layout.review.layout_review_support import (
    LayoutReviewFixture,
)


def _configuration() -> CocoLayoutProposalConfiguration:
    return CocoLayoutProposalConfiguration(
        profile=CocoLayoutProfile.koios_doclaynet_v0_1(),
        detector_name="fixture-doclaynet-detector",
        detector_version="1.0",
        runtime_name="fixture-runtime",
        runtime_version="1.0",
        resource_identity="fixture:doclaynet-layout-model",
        resource_sha256=SHA256Hash("c" * 64),
    )


@pytest.mark.parametrize(
    ("category_id", "name", "kind"),
    (
        (1, "Caption", LayoutRegionKind.CAPTION),
        (2, "Footnote", LayoutRegionKind.FOOTNOTE),
        (3, "Formula", LayoutRegionKind.EQUATION),
        (4, "List-item", LayoutRegionKind.LIST),
        (5, "Page-footer", LayoutRegionKind.FOOTER),
        (6, "Page-header", LayoutRegionKind.HEADER),
        (7, "Picture", LayoutRegionKind.FIGURE),
        (8, "Section-header", LayoutRegionKind.TITLE),
        (9, "Table", LayoutRegionKind.TABLE),
        (10, "Text", LayoutRegionKind.TEXT),
        (11, "Title", LayoutRegionKind.TITLE),
    ),
)
def test_doclaynet_registry_has_exact_semantic_mapping(
    category_id: int,
    name: str,
    kind: LayoutRegionKind,
) -> None:
    category = CocoLayoutCategoryInventory.doclaynet_v1().require(category_id)

    assert category.name == name
    assert category.kind is kind


def test_doclaynet_registry_and_profile_identities_are_pinned() -> None:
    categories = CocoLayoutCategoryInventory.doclaynet_v1()

    assert len(categories) == 11
    assert categories.inventory_id == (
        "coco-layout-category-inventory:sha256:"
        "d5df2bbf88de955f31dabe880102e245dc80924c7235461bf8eee64085ec922e"
    )
    assert CocoLayoutProfile.koios_doclaynet_v0_1().profile_id == (
        "coco-layout-profile:sha256:"
        "e4bcd881d980c69bf94c9ce95d98d7709707b2bb417cd513e7bc3e9f41726c33"
    )


@pytest.mark.parametrize(
    ("media_type", "expected_name"),
    (
        ("image/jpeg", "images/00000007.jpg"),
        ("image/png", "images/00000007.png"),
        ("image/webp", "images/00000007.webp"),
    ),
)
def test_coco_image_has_deterministic_bundle_local_name(
    media_type: str,
    expected_name: str,
) -> None:
    image = CocoLayoutImage(
        image_id=7,
        render_id="render:fixture",
        width=100,
        height=200,
        image_media_type=media_type,
        image_sha256=SHA256Hash("a" * 64),
    )

    assert image.bundle_file_name == expected_name


def test_profile_v0_1_rejects_category_registry_drift() -> None:
    with pytest.raises(ValueError, match="categories differ"):
        CocoLayoutProfile(
            name=CocoLayoutProfile.KOIOS_PROFILE_NAME,
            version=CocoLayoutProfile.KOIOS_PROFILE_VERSION,
            categories=CocoLayoutCategoryInventory(
                CocoLayoutCategory(1, "Text", LayoutRegionKind.TEXT)
            ),
        )


def test_coco_xywh_detections_adapt_losslessly_to_domain_proposals() -> None:
    _, _, render = LayoutReviewFixture().render_evidence()
    image = CocoLayoutImage(
        image_id=7,
        render_id=render.render_id,
        width=render.image_width,
        height=render.image_height,
        image_media_type=render.image_media_type,
        image_sha256=render.image_sha256,
    )
    detections = CocoLayoutDetectionInventory(
        CocoLayoutDetection(
            annotation_id=10,
            image_id=7,
            category_id=10,
            bbox_xywh_pixels=(20.0, 20.0, 60.0, 20.0),
            confidence=0.95,
        ),
        CocoLayoutDetection(
            annotation_id=11,
            image_id=7,
            category_id=3,
            bbox_xywh_pixels=(20.0, 80.0, 60.0, 20.0),
            confidence=0.9,
        ),
    )
    request = CocoLayoutProposalRequest(
        render=render,
        image=image,
        detections=detections,
        configuration=_configuration(),
    )

    result = CocoLayoutRegionProposalActionizer().action(request=request)

    assert tuple(proposal.kind for proposal in result.proposals) == (
        LayoutRegionKind.TEXT,
        LayoutRegionKind.EQUATION,
    )
    assert result.proposals[0].bounding_box_pixels == (
        20.0,
        20.0,
        80.0,
        40.0,
    )
    assert result.proposal_source.detector_name == (
        "coco:fixture-doclaynet-detector"
    )
    assert result == type(result)(request=request)
    assert result.result_id == type(result)(request=request).result_id


@pytest.mark.parametrize(
    ("category_id", "bbox", "expected_message"),
    (
        (99, (0.0, 0.0, 1.0, 1.0), "unknown category"),
        (10, (199.0, 199.0, 2.0, 2.0), "exceeds image bounds"),
    ),
)
def test_coco_request_rejects_invalid_detection(
    category_id: int,
    bbox: tuple[float, float, float, float],
    expected_message: str,
) -> None:
    _, _, render = LayoutReviewFixture().render_evidence()
    image = CocoLayoutImage(
        image_id=7,
        render_id=render.render_id,
        width=render.image_width,
        height=render.image_height,
        image_media_type=render.image_media_type,
        image_sha256=render.image_sha256,
    )
    detections = CocoLayoutDetectionInventory(
        CocoLayoutDetection(
            annotation_id=1,
            image_id=7,
            category_id=category_id,
            bbox_xywh_pixels=bbox,
            confidence=1.0,
        )
    )

    with pytest.raises(ValueError, match=expected_message):
        CocoLayoutProposalRequest(
            render=render,
            image=image,
            detections=detections,
            configuration=_configuration(),
        )


def test_coco_category_registry_rejects_ambiguous_ordering() -> None:
    with pytest.raises(ValueError, match="sorted by category_id"):
        CocoLayoutCategoryInventory(
            CocoLayoutCategory(2, "Text", LayoutRegionKind.TEXT),
            CocoLayoutCategory(1, "Title", LayoutRegionKind.TITLE),
        )


def test_coco_detection_inventory_rejects_ambiguous_ordering() -> None:
    first = CocoLayoutDetection(
        annotation_id=1,
        image_id=1,
        category_id=10,
        bbox_xywh_pixels=(0.0, 0.0, 1.0, 1.0),
        confidence=1.0,
    )
    second = replace(first, annotation_id=2)

    with pytest.raises(ValueError, match="sorted by annotation_id"):
        CocoLayoutDetectionInventory(second, first)
