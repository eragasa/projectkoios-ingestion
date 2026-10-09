"""Complete internally verified Koios COCO Layout Profile v0.1 bundles."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.adaptation import (
    CocoLayoutProposalAdaptation,
)
from projectkoios.ingestion.integrations.coco.layout.document import (
    CocoLayoutAnnotationDocument,
)
from projectkoios.ingestion.integrations.coco.layout.json.annotations import (
    CocoLayoutAnnotationsJsonContract,
)
from projectkoios.ingestion.integrations.coco.layout.json.lineage import (
    CocoLayoutLineageJsonContract,
)
from projectkoios.ingestion.integrations.coco.layout.json.manifest import (
    CocoLayoutManifestJsonContract,
)
from projectkoios.ingestion.integrations.coco.layout.json.reading.order import (
    CocoLayoutReadingOrderJsonContract,
)
from projectkoios.ingestion.integrations.coco.layout.lineage import (
    CocoLayoutAnnotationLineage,
    CocoLayoutAnnotationLineageInventory,
    CocoLayoutAnnotationNativeBlockMembershipInventory,
    CocoLayoutLineageDocument,
)
from projectkoios.ingestion.integrations.coco.layout.manifest import (
    CocoLayoutBundleManifest,
    CocoLayoutBundleMember,
    CocoLayoutBundleMemberInventory,
    CocoLayoutBundleMemberName,
)
from projectkoios.ingestion.integrations.coco.layout.reading.order import (
    CocoLayoutImageReadingOrderInventory,
    CocoLayoutReadingOrderDocument,
)
from projectkoios.ingestion.integrations.coco.layout.result import (
    CocoLayoutProposalResult,
)
from projectkoios.ingestion.layout.proposal.region import LayoutRegionProposal
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter


@dataclass(frozen=True, slots=True)
class CocoLayoutBundle(AbstractImmutableDataObject):
    """Own four mutually bound canonical profile-v0.1 bundle documents."""

    CONTRACT_NAME: ClassVar[str] = "coco-layout-bundle"
    CONTRACT_VERSION: ClassVar[str] = "0.1"

    annotations: CocoLayoutAnnotationDocument
    reading_order: CocoLayoutReadingOrderDocument
    lineage: CocoLayoutLineageDocument
    manifest: CocoLayoutBundleManifest
    bundle_id: str = field(init=False)

    @classmethod
    def create(
        cls,
        *,
        annotations: CocoLayoutAnnotationDocument,
        proposal_result: CocoLayoutProposalResult,
        orders: CocoLayoutImageReadingOrderInventory,
        native_block_memberships: (
            CocoLayoutAnnotationNativeBlockMembershipInventory
        ),
    ) -> CocoLayoutBundle:
        """Create sidecars and a manifest from exact adaptation evidence."""
        if type(annotations) is not CocoLayoutAnnotationDocument:
            raise TypeError("annotations must be CocoLayoutAnnotationDocument")
        if type(proposal_result) is not CocoLayoutProposalResult:
            raise TypeError("proposal_result must be CocoLayoutProposalResult")
        if type(orders) is not CocoLayoutImageReadingOrderInventory:
            raise TypeError(
                "orders must be CocoLayoutImageReadingOrderInventory"
            )
        if type(native_block_memberships) is not (
            CocoLayoutAnnotationNativeBlockMembershipInventory
        ):
            raise TypeError(
                "native_block_memberships must be its exact inventory"
            )
        request = proposal_result.request
        if len(annotations.images) != 1:
            raise ValueError(
                "one proposal result requires exactly one COCO image"
            )
        image = next(iter(annotations.images))
        if image != request.image:
            raise ValueError(
                "COCO annotations image differs from proposal request"
            )
        if annotations.detections != request.detections:
            raise ValueError(
                "COCO annotations detections differ from proposal request"
            )
        if annotations.profile != request.configuration.profile:
            raise ValueError(
                "COCO annotations profile differs from configuration"
            )
        detection_ids = {
            detection.annotation_id for detection in annotations.detections
        }
        membership_ids = {
            membership.annotation_id for membership in native_block_memberships
        }
        if membership_ids != detection_ids:
            raise ValueError(
                "native-block memberships must exactly cover detections"
            )
        annotations_bytes = CocoLayoutAnnotationsJsonContract().serialize_bytes(
            annotations
        )
        annotations_sha256 = SHA256Fingerprinter.fingerprint(
            content=annotations_bytes
        )
        reading_order = CocoLayoutReadingOrderDocument(
            annotations_sha256=annotations_sha256,
            orders=orders,
        )
        lineage = CocoLayoutLineageDocument(
            annotations_sha256=annotations_sha256,
            profile_id=annotations.profile.profile_id,
            configuration_id=request.configuration.configuration_id,
            proposal_source_id=proposal_result.proposal_source.proposal_source_id,
            entries=CocoLayoutAnnotationLineageInventory(
                *(
                    CocoLayoutAnnotationLineage(
                        annotation_id=adaptation.detection.annotation_id,
                        detection_id=adaptation.detection.detection_id,
                        proposal_id=adaptation.proposal.proposal_id,
                        adaptation_id=adaptation.adaptation_id,
                        native_block_membership_status=(
                            native_block_memberships.require(
                                adaptation.detection.annotation_id
                            ).status
                        ),
                        native_block_ids=native_block_memberships.require(
                            adaptation.detection.annotation_id
                        ).block_ids,
                    )
                    for adaptation in proposal_result.adaptations
                )
            ),
        )
        reading_order_bytes = (
            CocoLayoutReadingOrderJsonContract().serialize_bytes(reading_order)
        )
        lineage_bytes = CocoLayoutLineageJsonContract().serialize_bytes(lineage)
        members = CocoLayoutBundleMemberInventory(
            CocoLayoutBundleMember.create(
                name=CocoLayoutBundleMemberName.ANNOTATIONS,
                document_id=annotations.document_id,
                content=annotations_bytes,
            ),
            CocoLayoutBundleMember.create(
                name=CocoLayoutBundleMemberName.LINEAGE,
                document_id=lineage.document_id,
                content=lineage_bytes,
            ),
            CocoLayoutBundleMember.create(
                name=CocoLayoutBundleMemberName.READING_ORDER,
                document_id=reading_order.document_id,
                content=reading_order_bytes,
            ),
        )
        return cls(
            annotations=annotations,
            reading_order=reading_order,
            lineage=lineage,
            manifest=CocoLayoutBundleManifest(
                profile_id=annotations.profile.profile_id,
                members=members,
            ),
        )

    @classmethod
    def from_member_bytes(
        cls,
        *,
        annotations: bytes,
        reading_order: bytes,
        lineage: bytes,
        manifest: bytes,
    ) -> CocoLayoutBundle:
        """Strictly parse and cross-validate all four canonical members."""
        return cls(
            annotations=CocoLayoutAnnotationsJsonContract().parse_bytes(
                annotations
            ),
            reading_order=CocoLayoutReadingOrderJsonContract().parse_bytes(
                reading_order
            ),
            lineage=CocoLayoutLineageJsonContract().parse_bytes(lineage),
            manifest=CocoLayoutManifestJsonContract().parse_bytes(manifest),
        )

    def __post_init__(self) -> None:
        self.validate_components(
            annotations=self.annotations,
            reading_order=self.reading_order,
            lineage=self.lineage,
            manifest=self.manifest,
        )
        object.__setattr__(
            self,
            "bundle_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                self.annotations.document_id,
                self.reading_order.document_id,
                self.lineage.document_id,
                self.manifest.manifest_id,
            ),
        )

    @classmethod
    def validate_components(
        cls,
        *,
        annotations: CocoLayoutAnnotationDocument,
        reading_order: CocoLayoutReadingOrderDocument,
        lineage: CocoLayoutLineageDocument,
        manifest: CocoLayoutBundleManifest,
    ) -> None:
        """Fail closed on digest, coverage, identity, or member drift."""
        if type(annotations) is not CocoLayoutAnnotationDocument:
            raise TypeError("annotations must be CocoLayoutAnnotationDocument")
        if type(reading_order) is not CocoLayoutReadingOrderDocument:
            raise TypeError(
                "reading_order must be CocoLayoutReadingOrderDocument"
            )
        if type(lineage) is not CocoLayoutLineageDocument:
            raise TypeError("lineage must be CocoLayoutLineageDocument")
        if type(manifest) is not CocoLayoutBundleManifest:
            raise TypeError("manifest must be CocoLayoutBundleManifest")
        annotations_bytes = CocoLayoutAnnotationsJsonContract().serialize_bytes(
            annotations
        )
        annotations_sha256 = SHA256Fingerprinter.fingerprint(
            content=annotations_bytes
        )
        if reading_order.annotations_sha256 != annotations_sha256:
            raise ValueError("reading order identifies other annotations bytes")
        if lineage.annotations_sha256 != annotations_sha256:
            raise ValueError("lineage identifies other annotations bytes")
        if lineage.profile_id != annotations.profile.profile_id:
            raise ValueError("lineage identifies another COCO profile")
        if manifest.profile_id != annotations.profile.profile_id:
            raise ValueError("manifest identifies another COCO profile")
        detections_by_image: dict[int, set[int]] = {
            image.image_id: set() for image in annotations.images
        }
        for detection in annotations.detections:
            detections_by_image[detection.image_id].add(detection.annotation_id)
        order_records_by_image = {
            order.image_id: order for order in reading_order.orders
        }
        annotation_orders_by_image = {
            image_id: set(order.annotation_order)
            for image_id, order in order_records_by_image.items()
        }
        if annotation_orders_by_image != detections_by_image:
            raise ValueError(
                "reading order must exactly cover annotations for every image"
            )
        entries_by_annotation = {
            entry.annotation_id: entry for entry in lineage.entries
        }
        annotation_ids = {
            detection.annotation_id for detection in annotations.detections
        }
        if set(entries_by_annotation) != annotation_ids:
            raise ValueError("lineage must exactly cover every annotation")
        native_blocks_by_image: dict[int, set[str]] = {
            image.image_id: set() for image in annotations.images
        }
        for detection in annotations.detections:
            image = annotations.images.require(detection.image_id)
            expected_adaptation = CocoLayoutProposalAdaptation(
                detection=detection,
                proposal=LayoutRegionProposal.create(
                    render_id=image.render_id,
                    proposal_source_id=lineage.proposal_source_id,
                    kind=annotations.profile.categories.require(
                        detection.category_id
                    ).kind,
                    bounding_box_pixels=detection.bounding_box_pixels,
                    confidence=detection.confidence,
                ),
            )
            entry = entries_by_annotation[detection.annotation_id]
            for block_id in entry.native_block_ids:
                if block_id in native_blocks_by_image[detection.image_id]:
                    raise ValueError(
                        "native block belongs to multiple COCO annotations"
                    )
                native_blocks_by_image[detection.image_id].add(block_id)
            if (
                entry.detection_id != detection.detection_id
                or entry.proposal_id != expected_adaptation.proposal.proposal_id
                or entry.adaptation_id != expected_adaptation.adaptation_id
            ):
                raise ValueError("lineage differs from annotation derivation")
        native_orders_by_image = {
            image_id: set(order.native_block_order)
            for image_id, order in order_records_by_image.items()
        }
        if native_orders_by_image != native_blocks_by_image:
            raise ValueError(
                "reading order must exactly cover native-block memberships"
            )
        reading_order_bytes = (
            CocoLayoutReadingOrderJsonContract().serialize_bytes(reading_order)
        )
        lineage_bytes = CocoLayoutLineageJsonContract().serialize_bytes(lineage)
        expected_members = CocoLayoutBundleMemberInventory(
            CocoLayoutBundleMember.create(
                name=CocoLayoutBundleMemberName.ANNOTATIONS,
                document_id=annotations.document_id,
                content=annotations_bytes,
            ),
            CocoLayoutBundleMember.create(
                name=CocoLayoutBundleMemberName.LINEAGE,
                document_id=lineage.document_id,
                content=lineage_bytes,
            ),
            CocoLayoutBundleMember.create(
                name=CocoLayoutBundleMemberName.READING_ORDER,
                document_id=reading_order.document_id,
                content=reading_order_bytes,
            ),
        )
        if manifest.members != expected_members:
            raise ValueError("manifest members differ from canonical documents")

    @property
    def annotations_bytes(self) -> bytes:
        """Return canonical ``annotations.coco.json`` bytes."""
        return CocoLayoutAnnotationsJsonContract().serialize_bytes(
            self.annotations
        )

    @property
    def reading_order_bytes(self) -> bytes:
        """Return canonical ``reading-order.json`` bytes."""
        return CocoLayoutReadingOrderJsonContract().serialize_bytes(
            self.reading_order
        )

    @property
    def lineage_bytes(self) -> bytes:
        """Return canonical ``lineage.json`` bytes."""
        return CocoLayoutLineageJsonContract().serialize_bytes(self.lineage)

    @property
    def manifest_bytes(self) -> bytes:
        """Return canonical ``manifest.json`` bytes."""
        return CocoLayoutManifestJsonContract().serialize_bytes(self.manifest)
