"""Canonical ``annotations.coco.json`` contract for layout bundles."""

from __future__ import annotations

from projectkoios.ingestion.integrations.coco.layout.category import (
    CocoLayoutCategory,
    CocoLayoutCategoryInventory,
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
from projectkoios.ingestion.integrations.coco.layout.json.base import (
    CocoLayoutJsonContract,
)
from projectkoios.ingestion.integrations.coco.layout.json.value import (
    CocoLayoutJsonValue,
)
from projectkoios.ingestion.integrations.coco.layout.profile import (
    CocoLayoutProfile,
)
from projectkoios.ingestion.json.value import JsonValue
from projectkoios.ingestion.layout.proposal.kind import LayoutRegionKind
from projectkoios.ingestion.sha256.hash import SHA256Hash


class CocoLayoutAnnotationsJsonContract(
    CocoLayoutJsonContract[CocoLayoutAnnotationDocument]
):
    """Reconstruct the exact Koios COCO Layout Profile v0.1 region document."""

    __slots__ = ()

    ROOT_FIELDS = frozenset(
        {
            "annotations",
            "categories",
            "images",
            "koios_profile",
            "schema_version",
        }
    )
    PROFILE_FIELDS = frozenset(
        {"coordinate_convention", "id", "name", "version"}
    )
    IMAGE_FIELDS = frozenset(
        {
            "file_name",
            "height",
            "id",
            "koios_image_media_type",
            "koios_image_sha256",
            "koios_render_id",
            "width",
        }
    )
    CATEGORY_FIELDS = frozenset(
        {"id", "koios_region_kind", "name", "supercategory"}
    )
    ANNOTATION_FIELDS = frozenset(
        {"area", "bbox", "category_id", "id", "image_id", "iscrowd", "score"}
    )

    def to_json_value(self, value: CocoLayoutAnnotationDocument) -> JsonValue:
        if type(value) is not CocoLayoutAnnotationDocument:
            raise TypeError("value must be CocoLayoutAnnotationDocument")
        return {
            "schema_version": value.CONTRACT_VERSION,
            "koios_profile": {
                "id": value.profile.profile_id,
                "name": value.profile.name,
                "version": value.profile.version,
                "coordinate_convention": (
                    value.profile.XYWH_COORDINATE_CONVENTION
                ),
            },
            "images": [
                {
                    "id": image.image_id,
                    "width": image.width,
                    "height": image.height,
                    "file_name": image.bundle_file_name,
                    "koios_render_id": image.render_id,
                    "koios_image_media_type": image.image_media_type,
                    "koios_image_sha256": image.image_sha256,
                }
                for image in value.images
            ],
            "categories": [
                {
                    "id": category.category_id,
                    "name": category.name,
                    "supercategory": "document-layout",
                    "koios_region_kind": category.kind.value,
                }
                for category in value.profile.categories
            ],
            "annotations": [
                {
                    "id": detection.annotation_id,
                    "image_id": detection.image_id,
                    "category_id": detection.category_id,
                    "bbox": list(detection.bbox_xywh_pixels),
                    "area": (
                        detection.bbox_xywh_pixels[2]
                        * detection.bbox_xywh_pixels[3]
                    ),
                    "iscrowd": 0,
                    "score": detection.confidence,
                }
                for detection in value.detections
            ],
        }

    def from_json_value(self, value: JsonValue) -> CocoLayoutAnnotationDocument:
        root = CocoLayoutJsonValue.require_object(
            value,
            field="annotations document",
            expected_fields=self.ROOT_FIELDS,
        )
        schema_version = CocoLayoutJsonValue.require_string(
            root["schema_version"], field="schema_version"
        )
        if schema_version != CocoLayoutAnnotationDocument.CONTRACT_VERSION:
            raise ValueError("unsupported COCO annotation schema version")
        categories = CocoLayoutCategoryInventory(
            *(
                self.category_from_json_value(item)
                for item in CocoLayoutJsonValue.require_array(
                    root["categories"], field="categories"
                )
            )
        )
        profile_value = CocoLayoutJsonValue.require_object(
            root["koios_profile"],
            field="koios_profile",
            expected_fields=self.PROFILE_FIELDS,
        )
        coordinate_convention = CocoLayoutJsonValue.require_string(
            profile_value["coordinate_convention"],
            field="koios_profile.coordinate_convention",
        )
        if (
            coordinate_convention
            != CocoLayoutProfile.XYWH_COORDINATE_CONVENTION
        ):
            raise ValueError("unsupported COCO coordinate convention")
        profile = CocoLayoutProfile(
            name=CocoLayoutJsonValue.require_string(
                profile_value["name"], field="koios_profile.name"
            ),
            version=CocoLayoutJsonValue.require_string(
                profile_value["version"], field="koios_profile.version"
            ),
            categories=categories,
        )
        profile_id = CocoLayoutJsonValue.require_string(
            profile_value["id"], field="koios_profile.id"
        )
        if profile_id != profile.profile_id:
            raise ValueError("COCO profile identity is inconsistent")
        images = CocoLayoutImageInventory(
            *(
                self.image_from_json_value(item)
                for item in CocoLayoutJsonValue.require_array(
                    root["images"], field="images"
                )
            )
        )
        detections = CocoLayoutDetectionInventory(
            *(
                self.annotation_from_json_value(item)
                for item in CocoLayoutJsonValue.require_array(
                    root["annotations"], field="annotations"
                )
            )
        )
        return CocoLayoutAnnotationDocument(
            profile=profile,
            images=images,
            detections=detections,
        )

    @classmethod
    def category_from_json_value(cls, value: JsonValue) -> CocoLayoutCategory:
        """Reconstruct one exact category entry."""
        item = CocoLayoutJsonValue.require_object(
            value,
            field="category",
            expected_fields=cls.CATEGORY_FIELDS,
        )
        supercategory = CocoLayoutJsonValue.require_string(
            item["supercategory"], field="category.supercategory"
        )
        if supercategory != "document-layout":
            raise ValueError("COCO category supercategory is inconsistent")
        kind_value = CocoLayoutJsonValue.require_string(
            item["koios_region_kind"], field="category.koios_region_kind"
        )
        try:
            kind = LayoutRegionKind(kind_value)
        except ValueError as error:
            raise ValueError("unknown Koios layout region kind") from error
        return CocoLayoutCategory(
            category_id=CocoLayoutJsonValue.require_integer(
                item["id"], field="category.id"
            ),
            name=CocoLayoutJsonValue.require_string(
                item["name"], field="category.name"
            ),
            kind=kind,
        )

    @classmethod
    def image_from_json_value(cls, value: JsonValue) -> CocoLayoutImage:
        """Reconstruct one locator-free image/render binding."""
        item = CocoLayoutJsonValue.require_object(
            value,
            field="image",
            expected_fields=cls.IMAGE_FIELDS,
        )
        render_id = CocoLayoutJsonValue.require_string(
            item["koios_render_id"], field="image.koios_render_id"
        )
        file_name = CocoLayoutJsonValue.require_string(
            item["file_name"], field="image.file_name"
        )
        image = CocoLayoutImage(
            image_id=CocoLayoutJsonValue.require_integer(
                item["id"], field="image.id"
            ),
            render_id=render_id,
            width=CocoLayoutJsonValue.require_integer(
                item["width"], field="image.width"
            ),
            height=CocoLayoutJsonValue.require_integer(
                item["height"], field="image.height"
            ),
            image_media_type=CocoLayoutJsonValue.require_string(
                item["koios_image_media_type"],
                field="image.koios_image_media_type",
            ),
            image_sha256=SHA256Hash(
                CocoLayoutJsonValue.require_string(
                    item["koios_image_sha256"],
                    field="image.koios_image_sha256",
                )
            ),
        )
        if file_name != image.bundle_file_name:
            raise ValueError("COCO image file_name is not deterministic")
        return image

    @classmethod
    def annotation_from_json_value(
        cls, value: JsonValue
    ) -> CocoLayoutDetection:
        """Reconstruct one exact box annotation and validate derived area."""
        item = CocoLayoutJsonValue.require_object(
            value,
            field="annotation",
            expected_fields=cls.ANNOTATION_FIELDS,
        )
        bbox_values = CocoLayoutJsonValue.require_array(
            item["bbox"], field="annotation.bbox"
        )
        if len(bbox_values) != 4:
            raise ValueError("annotation.bbox must contain four numbers")
        bbox = tuple(
            CocoLayoutJsonValue.require_number(
                component, field="annotation.bbox component"
            )
            for component in bbox_values
        )
        area = CocoLayoutJsonValue.require_number(
            item["area"], field="annotation.area"
        )
        if area != bbox[2] * bbox[3]:
            raise ValueError("COCO annotation area differs from its box")
        iscrowd = CocoLayoutJsonValue.require_integer(
            item["iscrowd"], field="annotation.iscrowd"
        )
        if iscrowd != 0:
            raise ValueError("Koios COCO layout annotations cannot be crowds")
        return CocoLayoutDetection(
            annotation_id=CocoLayoutJsonValue.require_integer(
                item["id"], field="annotation.id"
            ),
            image_id=CocoLayoutJsonValue.require_integer(
                item["image_id"], field="annotation.image_id"
            ),
            category_id=CocoLayoutJsonValue.require_integer(
                item["category_id"], field="annotation.category_id"
            ),
            bbox_xywh_pixels=(bbox[0], bbox[1], bbox[2], bbox[3]),
            confidence=CocoLayoutJsonValue.require_number(
                item["score"], field="annotation.score"
            ),
        )
