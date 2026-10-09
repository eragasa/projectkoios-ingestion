"""Koios COCO Layout Profile v0.1 bundle tests."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from typing import Any

import pytest
from projectkoios.ingestion.integrations.coco.layout.bundle import (
    CocoLayoutBundle,
)
from projectkoios.ingestion.integrations.coco.layout.json.annotations import (
    CocoLayoutAnnotationsJsonContract,
)
from projectkoios.ingestion.integrations.coco.layout.lineage import (
    CocoLayoutAnnotationLineage,
    CocoLayoutAnnotationLineageInventory,
    CocoLayoutAnnotationNativeBlockMembership,
    CocoLayoutLineageDocument,
    CocoLayoutNativeBlockIdentityInventory,
    CocoLayoutNativeBlockMembershipStatus,
)
from projectkoios.ingestion.integrations.coco.layout.manifest import (
    CocoLayoutBundleManifest,
    CocoLayoutBundleMember,
    CocoLayoutBundleMemberInventory,
    CocoLayoutBundleMemberName,
)
from projectkoios.ingestion.integrations.coco.layout.reading.order import (
    CocoLayoutAnnotationOrder,
    CocoLayoutImageReadingOrder,
    CocoLayoutImageReadingOrderInventory,
    CocoLayoutNativeBlockOrder,
    CocoLayoutReadingOrderDocument,
)
from projectkoios.ingestion.json.error import (
    JsonDuplicateFieldError,
    JsonParseError,
)
from projectkoios.ingestion.sha256.hash import SHA256Hash

from tests.projectkoios.ingestion.integrations.coco.layout.fixture import (
    coco_layout_bundle_fixture,
)


def _canonical_mutation(
    content: bytes,
    mutation: Callable[[dict[str, Any]], None],
) -> bytes:
    value: dict[str, Any] = json.loads(content)
    mutation(value)
    return CocoLayoutAnnotationsJsonContract().serializer.serialize_bytes(value)


def test_profile_v0_1_bundle_round_trips_all_four_canonical_members() -> None:
    bundle = coco_layout_bundle_fixture()

    reconstructed = CocoLayoutBundle.from_member_bytes(
        annotations=bundle.annotations_bytes,
        reading_order=bundle.reading_order_bytes,
        lineage=bundle.lineage_bytes,
        manifest=bundle.manifest_bytes,
    )

    assert reconstructed == bundle
    assert reconstructed.bundle_id == bundle.bundle_id
    assert tuple(member.name for member in bundle.manifest.members) == (
        CocoLayoutBundleMemberName.ANNOTATIONS,
        CocoLayoutBundleMemberName.LINEAGE,
        CocoLayoutBundleMemberName.READING_ORDER,
    )
    assert bundle.annotations.detections == reconstructed.annotations.detections
    detections = tuple(reconstructed.annotations.detections)
    assert detections[0].bbox_xywh_pixels == (20.0, 80.0, 60.0, 20.0)
    assert detections[1].bbox_xywh_pixels == (
        20.25,
        20.5,
        59.5,
        19.25,
    )
    image = next(iter(reconstructed.annotations.images))
    assert image.bundle_file_name == "images/00000001.png"
    assert image.image_sha256 == SHA256Hash("a" * 64)
    entries = tuple(reconstructed.lineage.entries)
    assert entries[0].native_block_membership_status is (
        CocoLayoutNativeBlockMembershipStatus.EVALUATED
    )
    assert tuple(entries[1].native_block_ids) == ("native-block:001",)


def test_annotations_contract_rejects_noncanonical_and_duplicate_json() -> None:
    content = coco_layout_bundle_fixture().annotations_bytes
    contract = CocoLayoutAnnotationsJsonContract()

    with pytest.raises(JsonParseError, match="canonical"):
        contract.parse_bytes(b" " + content)
    duplicate = content.replace(
        b"{",
        b'{"schema_version":"0.1",',
        1,
    )
    with pytest.raises(JsonDuplicateFieldError):
        contract.parse_bytes(duplicate)


@pytest.mark.parametrize(
    ("drift", "expected_message"),
    (
        ("area", "area differs"),
        ("category", "unknown category"),
        ("annotation_order", "sorted by annotation_id"),
        ("annotation_id_assignment", "canonical semantic order"),
        ("image_id_assignment", "contiguous from one"),
    ),
)
def test_annotations_contract_rejects_semantic_drift(
    drift: str,
    expected_message: str,
) -> None:
    content = coco_layout_bundle_fixture().annotations_bytes

    def mutate(value: dict[str, Any]) -> None:
        if drift == "area":
            value["annotations"][0]["area"] = 1.0
        elif drift == "category":
            value["annotations"][1]["category_id"] = 999
        elif drift == "annotation_order":
            value["annotations"].reverse()
        elif drift == "annotation_id_assignment":
            value["annotations"][0]["category_id"] = 11
        elif drift == "image_id_assignment":
            value["images"][0]["id"] = 2
            value["images"][0]["file_name"] = "images/00000002.png"
            for annotation in value["annotations"]:
                annotation["image_id"] = 2
        else:
            raise AssertionError(f"unknown test drift: {drift}")

    altered = _canonical_mutation(content, mutate)

    with pytest.raises(ValueError, match=expected_message):
        CocoLayoutAnnotationsJsonContract().parse_bytes(altered)


def test_bundle_rejects_incomplete_annotation_order() -> None:
    bundle = coco_layout_bundle_fixture()
    incomplete_order = CocoLayoutReadingOrderDocument(
        annotations_sha256=bundle.reading_order.annotations_sha256,
        orders=CocoLayoutImageReadingOrderInventory(
            CocoLayoutImageReadingOrder(
                image_id=1,
                annotation_order=CocoLayoutAnnotationOrder(2),
                native_block_order=CocoLayoutNativeBlockOrder(
                    "native-block:001"
                ),
            )
        ),
    )

    with pytest.raises(ValueError, match="exactly cover"):
        CocoLayoutBundle(
            annotations=bundle.annotations,
            reading_order=incomplete_order,
            lineage=bundle.lineage,
            manifest=bundle.manifest,
        )


def test_bundle_rejects_incomplete_native_block_order() -> None:
    bundle = coco_layout_bundle_fixture()
    missing_native_order = CocoLayoutReadingOrderDocument(
        annotations_sha256=bundle.reading_order.annotations_sha256,
        orders=CocoLayoutImageReadingOrderInventory(
            CocoLayoutImageReadingOrder(
                image_id=1,
                annotation_order=CocoLayoutAnnotationOrder(2, 1),
                native_block_order=CocoLayoutNativeBlockOrder(),
            )
        ),
    )

    with pytest.raises(ValueError, match="native-block memberships"):
        CocoLayoutBundle(
            annotations=bundle.annotations,
            reading_order=missing_native_order,
            lineage=bundle.lineage,
            manifest=bundle.manifest,
        )


def test_bundle_rejects_forged_lineage() -> None:
    bundle = coco_layout_bundle_fixture()
    entries = tuple(bundle.lineage.entries)
    forged_entry = CocoLayoutAnnotationLineage(
        annotation_id=entries[0].annotation_id,
        detection_id="forged-detection",
        proposal_id=entries[0].proposal_id,
        adaptation_id=entries[0].adaptation_id,
        native_block_membership_status=(
            entries[0].native_block_membership_status
        ),
        native_block_ids=entries[0].native_block_ids,
    )
    forged_lineage = CocoLayoutLineageDocument(
        annotations_sha256=bundle.lineage.annotations_sha256,
        profile_id=bundle.lineage.profile_id,
        configuration_id=bundle.lineage.configuration_id,
        proposal_source_id=bundle.lineage.proposal_source_id,
        entries=CocoLayoutAnnotationLineageInventory(
            forged_entry,
            *entries[1:],
        ),
    )

    with pytest.raises(ValueError, match="annotation derivation"):
        CocoLayoutBundle(
            annotations=bundle.annotations,
            reading_order=bundle.reading_order,
            lineage=forged_lineage,
            manifest=bundle.manifest,
        )


def test_bundle_rejects_manifest_digest_drift() -> None:
    bundle = coco_layout_bundle_fixture()
    members = tuple(bundle.manifest.members)
    altered_annotations = replace(
        members[0],
        sha256=SHA256Hash("d" * 64),
    )
    altered_manifest = CocoLayoutBundleManifest(
        profile_id=bundle.manifest.profile_id,
        members=CocoLayoutBundleMemberInventory(
            altered_annotations,
            *members[1:],
        ),
    )

    with pytest.raises(ValueError, match="canonical documents"):
        CocoLayoutBundle(
            annotations=bundle.annotations,
            reading_order=bundle.reading_order,
            lineage=bundle.lineage,
            manifest=altered_manifest,
        )


def test_manifest_requires_complete_fixed_member_registry() -> None:
    bundle = coco_layout_bundle_fixture()
    annotations_member = bundle.manifest.members.require(
        CocoLayoutBundleMemberName.ANNOTATIONS
    )

    with pytest.raises(ValueError, match="complete and sorted"):
        CocoLayoutBundleMemberInventory(annotations_member)


def test_not_evaluated_membership_rejects_native_block_ids() -> None:
    with pytest.raises(ValueError, match="cannot identify native blocks"):
        CocoLayoutAnnotationNativeBlockMembership(
            annotation_id=1,
            status=CocoLayoutNativeBlockMembershipStatus.NOT_EVALUATED,
            block_ids=CocoLayoutNativeBlockIdentityInventory(
                "native-block:001"
            ),
        )


def test_manifest_member_rejects_zero_length_content() -> None:
    bundle = coco_layout_bundle_fixture()

    with pytest.raises(ValueError, match="positive integer"):
        CocoLayoutBundleMember(
            name=CocoLayoutBundleMemberName.ANNOTATIONS,
            document_id=bundle.annotations.document_id,
            sha256=SHA256Hash("a" * 64),
            byte_length=0,
        )
