"""Reusable Koios COCO Layout Profile v0.1 test fixtures."""

from projectkoios.ingestion.integrations.coco.layout.actionizer import (
    CocoLayoutRegionProposalActionizer,
)
from projectkoios.ingestion.integrations.coco.layout.bundle import (
    CocoLayoutBundle,
)
from projectkoios.ingestion.integrations.coco.layout.configuration import (
    CocoLayoutProposalConfiguration,
)
from projectkoios.ingestion.integrations.coco.layout.detection import (
    CocoLayoutDetection,
    CocoLayoutDetectionInventory,
)
from projectkoios.ingestion.integrations.coco.layout.document import (
    CocoLayoutAnnotationDocument,
)
from projectkoios.ingestion.integrations.coco.layout.image import (
    CocoLayoutImage,
    CocoLayoutImageInventory,
)
from projectkoios.ingestion.integrations.coco.layout.lineage import (
    CocoLayoutAnnotationNativeBlockMembership,
    CocoLayoutAnnotationNativeBlockMembershipInventory,
    CocoLayoutNativeBlockIdentityInventory,
    CocoLayoutNativeBlockMembershipStatus,
)
from projectkoios.ingestion.integrations.coco.layout.profile import (
    CocoLayoutProfile,
)
from projectkoios.ingestion.integrations.coco.layout.reading.order import (
    CocoLayoutAnnotationOrder,
    CocoLayoutImageReadingOrder,
    CocoLayoutImageReadingOrderInventory,
    CocoLayoutNativeBlockOrder,
)
from projectkoios.ingestion.integrations.coco.layout.request import (
    CocoLayoutProposalRequest,
)
from projectkoios.ingestion.sha256.hash import SHA256Hash

from tests.projectkoios.ingestion.layout.review.layout_review_support import (
    LayoutReviewFixture,
)


def coco_layout_bundle_fixture() -> CocoLayoutBundle:
    """Build one deterministic two-annotation profile bundle."""
    _, _, render = LayoutReviewFixture().render_evidence()
    profile = CocoLayoutProfile.koios_doclaynet_v0_1()
    image = CocoLayoutImage(
        image_id=1,
        render_id=render.render_id,
        width=render.image_width,
        height=render.image_height,
        image_media_type=render.image_media_type,
        image_sha256=render.image_sha256,
    )
    detections = CocoLayoutDetectionInventory(
        CocoLayoutDetection(
            annotation_id=1,
            image_id=1,
            category_id=3,
            bbox_xywh_pixels=(20.0, 80.0, 60.0, 20.0),
            confidence=0.9,
        ),
        CocoLayoutDetection(
            annotation_id=2,
            image_id=1,
            category_id=10,
            bbox_xywh_pixels=(20.25, 20.5, 59.5, 19.25),
            confidence=0.95,
        ),
    )
    configuration = CocoLayoutProposalConfiguration(
        profile=profile,
        detector_name="fixture-doclaynet-detector",
        detector_version="1.0",
        runtime_name="fixture-runtime",
        runtime_version="1.0",
        resource_identity="fixture:doclaynet-layout-model",
        resource_sha256=SHA256Hash("c" * 64),
    )
    proposal_result = CocoLayoutRegionProposalActionizer().action(
        request=CocoLayoutProposalRequest(
            render=render,
            image=image,
            detections=detections,
            configuration=configuration,
        )
    )
    annotations = CocoLayoutAnnotationDocument(
        profile=profile,
        images=CocoLayoutImageInventory(image),
        detections=detections,
    )
    orders = CocoLayoutImageReadingOrderInventory(
        CocoLayoutImageReadingOrder(
            image_id=1,
            annotation_order=CocoLayoutAnnotationOrder(2, 1),
            native_block_order=CocoLayoutNativeBlockOrder("native-block:001"),
        )
    )
    return CocoLayoutBundle.create(
        annotations=annotations,
        proposal_result=proposal_result,
        orders=orders,
        native_block_memberships=(
            CocoLayoutAnnotationNativeBlockMembershipInventory(
                CocoLayoutAnnotationNativeBlockMembership(
                    annotation_id=1,
                    status=CocoLayoutNativeBlockMembershipStatus.EVALUATED,
                    block_ids=CocoLayoutNativeBlockIdentityInventory(),
                ),
                CocoLayoutAnnotationNativeBlockMembership(
                    annotation_id=2,
                    status=CocoLayoutNativeBlockMembershipStatus.EVALUATED,
                    block_ids=CocoLayoutNativeBlockIdentityInventory(
                        "native-block:001"
                    ),
                ),
            )
        ),
    )
