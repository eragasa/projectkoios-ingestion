"""Canonical ``lineage.json`` contract for COCO layout bundles."""

from __future__ import annotations

from projectkoios.ingestion.integrations.coco.layout.json.base import (
    CocoLayoutJsonContract,
)
from projectkoios.ingestion.integrations.coco.layout.json.value import (
    CocoLayoutJsonValue,
)
from projectkoios.ingestion.integrations.coco.layout.lineage import (
    CocoLayoutAnnotationLineage,
    CocoLayoutAnnotationLineageInventory,
    CocoLayoutLineageDocument,
    CocoLayoutNativeBlockIdentityInventory,
    CocoLayoutNativeBlockMembershipStatus,
)
from projectkoios.ingestion.json.value import JsonValue
from projectkoios.ingestion.sha256.hash import SHA256Hash


class CocoLayoutLineageJsonContract(
    CocoLayoutJsonContract[CocoLayoutLineageDocument]
):
    """Reconstruct the exact digest-bound COCO proposal-lineage sidecar."""

    __slots__ = ()

    ROOT_FIELDS = frozenset(
        {
            "annotations_sha256",
            "configuration_id",
            "entries",
            "profile_id",
            "proposal_source_id",
            "schema_version",
        }
    )
    ENTRY_FIELDS = frozenset(
        {
            "adaptation_id",
            "annotation_id",
            "detection_id",
            "native_block_ids",
            "native_block_membership_status",
            "proposal_id",
        }
    )

    def to_json_value(self, value: CocoLayoutLineageDocument) -> JsonValue:
        if type(value) is not CocoLayoutLineageDocument:
            raise TypeError("value must be CocoLayoutLineageDocument")
        return {
            "schema_version": value.CONTRACT_VERSION,
            "annotations_sha256": value.annotations_sha256,
            "profile_id": value.profile_id,
            "configuration_id": value.configuration_id,
            "proposal_source_id": value.proposal_source_id,
            "entries": [
                {
                    "annotation_id": entry.annotation_id,
                    "detection_id": entry.detection_id,
                    "proposal_id": entry.proposal_id,
                    "adaptation_id": entry.adaptation_id,
                    "native_block_membership_status": (
                        entry.native_block_membership_status.value
                    ),
                    "native_block_ids": list(entry.native_block_ids),
                }
                for entry in value.entries
            ],
        }

    def from_json_value(self, value: JsonValue) -> CocoLayoutLineageDocument:
        root = CocoLayoutJsonValue.require_object(
            value,
            field="lineage document",
            expected_fields=self.ROOT_FIELDS,
        )
        version = CocoLayoutJsonValue.require_string(
            root["schema_version"], field="schema_version"
        )
        if version != CocoLayoutLineageDocument.CONTRACT_VERSION:
            raise ValueError("unsupported lineage schema version")
        entries = CocoLayoutAnnotationLineageInventory(
            *(
                self.entry_from_json_value(item)
                for item in CocoLayoutJsonValue.require_array(
                    root["entries"], field="entries"
                )
            )
        )
        return CocoLayoutLineageDocument(
            annotations_sha256=SHA256Hash(
                CocoLayoutJsonValue.require_string(
                    root["annotations_sha256"],
                    field="annotations_sha256",
                )
            ),
            profile_id=CocoLayoutJsonValue.require_string(
                root["profile_id"], field="profile_id"
            ),
            configuration_id=CocoLayoutJsonValue.require_string(
                root["configuration_id"], field="configuration_id"
            ),
            proposal_source_id=CocoLayoutJsonValue.require_string(
                root["proposal_source_id"], field="proposal_source_id"
            ),
            entries=entries,
        )

    @classmethod
    def entry_from_json_value(
        cls, value: JsonValue
    ) -> CocoLayoutAnnotationLineage:
        """Reconstruct one exact annotation lineage entry."""
        item = CocoLayoutJsonValue.require_object(
            value,
            field="lineage entry",
            expected_fields=cls.ENTRY_FIELDS,
        )
        return CocoLayoutAnnotationLineage(
            annotation_id=CocoLayoutJsonValue.require_integer(
                item["annotation_id"], field="lineage annotation_id"
            ),
            detection_id=CocoLayoutJsonValue.require_string(
                item["detection_id"], field="lineage detection_id"
            ),
            proposal_id=CocoLayoutJsonValue.require_string(
                item["proposal_id"], field="lineage proposal_id"
            ),
            adaptation_id=CocoLayoutJsonValue.require_string(
                item["adaptation_id"], field="lineage adaptation_id"
            ),
            native_block_membership_status=(
                CocoLayoutNativeBlockMembershipStatus(
                    CocoLayoutJsonValue.require_string(
                        item["native_block_membership_status"],
                        field="lineage native block membership status",
                    )
                )
            ),
            native_block_ids=CocoLayoutNativeBlockIdentityInventory(
                *(
                    CocoLayoutJsonValue.require_string(
                        block_id,
                        field="lineage native block ID",
                    )
                    for block_id in CocoLayoutJsonValue.require_array(
                        item["native_block_ids"],
                        field="lineage native_block_ids",
                    )
                )
            ),
        )
