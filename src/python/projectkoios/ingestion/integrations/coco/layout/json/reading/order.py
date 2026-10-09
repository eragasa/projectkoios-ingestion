"""Canonical ``reading-order.json`` contract for COCO layout bundles."""

from __future__ import annotations

from projectkoios.ingestion.integrations.coco.layout.json.base import (
    CocoLayoutJsonContract,
)
from projectkoios.ingestion.integrations.coco.layout.json.value import (
    CocoLayoutJsonValue,
)
from projectkoios.ingestion.integrations.coco.layout.reading.order import (
    CocoLayoutAnnotationOrder,
    CocoLayoutImageReadingOrder,
    CocoLayoutImageReadingOrderInventory,
    CocoLayoutNativeBlockOrder,
    CocoLayoutReadingOrderDocument,
)
from projectkoios.ingestion.json.value import JsonValue
from projectkoios.ingestion.sha256.hash import SHA256Hash


class CocoLayoutReadingOrderJsonContract(
    CocoLayoutJsonContract[CocoLayoutReadingOrderDocument]
):
    """Reconstruct the digest-bound Koios reading-order sidecar."""

    __slots__ = ()

    ROOT_FIELDS = frozenset({"annotations_sha256", "orders", "schema_version"})
    ORDER_FIELDS = frozenset({"annotation_ids", "image_id", "native_block_ids"})

    def to_json_value(self, value: CocoLayoutReadingOrderDocument) -> JsonValue:
        if type(value) is not CocoLayoutReadingOrderDocument:
            raise TypeError("value must be CocoLayoutReadingOrderDocument")
        return {
            "schema_version": value.CONTRACT_VERSION,
            "annotations_sha256": value.annotations_sha256,
            "orders": [
                {
                    "image_id": order.image_id,
                    "annotation_ids": list(order.annotation_order),
                    "native_block_ids": list(order.native_block_order),
                }
                for order in value.orders
            ],
        }

    def from_json_value(
        self, value: JsonValue
    ) -> CocoLayoutReadingOrderDocument:
        root = CocoLayoutJsonValue.require_object(
            value,
            field="reading-order document",
            expected_fields=self.ROOT_FIELDS,
        )
        version = CocoLayoutJsonValue.require_string(
            root["schema_version"], field="schema_version"
        )
        if version != CocoLayoutReadingOrderDocument.CONTRACT_VERSION:
            raise ValueError("unsupported reading-order schema version")
        orders = CocoLayoutImageReadingOrderInventory(
            *(
                self.order_from_json_value(item)
                for item in CocoLayoutJsonValue.require_array(
                    root["orders"], field="orders"
                )
            )
        )
        return CocoLayoutReadingOrderDocument(
            annotations_sha256=SHA256Hash(
                CocoLayoutJsonValue.require_string(
                    root["annotations_sha256"],
                    field="annotations_sha256",
                )
            ),
            orders=orders,
        )

    @classmethod
    def order_from_json_value(
        cls, value: JsonValue
    ) -> CocoLayoutImageReadingOrder:
        """Reconstruct one per-image complete order."""
        item = CocoLayoutJsonValue.require_object(
            value,
            field="reading order",
            expected_fields=cls.ORDER_FIELDS,
        )
        annotation_ids = CocoLayoutJsonValue.require_array(
            item["annotation_ids"], field="reading order.annotation_ids"
        )
        return CocoLayoutImageReadingOrder(
            image_id=CocoLayoutJsonValue.require_integer(
                item["image_id"], field="reading order.image_id"
            ),
            annotation_order=CocoLayoutAnnotationOrder(
                *(
                    CocoLayoutJsonValue.require_integer(
                        annotation_id,
                        field="reading order annotation ID",
                    )
                    for annotation_id in annotation_ids
                )
            ),
            native_block_order=CocoLayoutNativeBlockOrder(
                *(
                    CocoLayoutJsonValue.require_string(
                        block_id,
                        field="reading order native block ID",
                    )
                    for block_id in CocoLayoutJsonValue.require_array(
                        item["native_block_ids"],
                        field="reading order native_block_ids",
                    )
                )
            ),
        )
