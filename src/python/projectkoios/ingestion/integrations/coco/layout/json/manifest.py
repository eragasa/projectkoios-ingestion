"""Canonical ``manifest.json`` contract for COCO layout bundles."""

from __future__ import annotations

from projectkoios.ingestion.integrations.coco.layout.json.base import (
    CocoLayoutJsonContract,
)
from projectkoios.ingestion.integrations.coco.layout.json.value import (
    CocoLayoutJsonValue,
)
from projectkoios.ingestion.integrations.coco.layout.manifest import (
    CocoLayoutBundleManifest,
    CocoLayoutBundleMember,
    CocoLayoutBundleMemberInventory,
    CocoLayoutBundleMemberName,
)
from projectkoios.ingestion.json.value import JsonValue
from projectkoios.ingestion.sha256.hash import SHA256Hash


class CocoLayoutManifestJsonContract(
    CocoLayoutJsonContract[CocoLayoutBundleManifest]
):
    """Reconstruct the exact digest manifest for profile-v0.1 bundles."""

    __slots__ = ()

    ROOT_FIELDS = frozenset({"id", "members", "profile_id", "schema_version"})
    MEMBER_FIELDS = frozenset(
        {"byte_length", "document_id", "media_type", "name", "sha256"}
    )

    def to_json_value(self, value: CocoLayoutBundleManifest) -> JsonValue:
        if type(value) is not CocoLayoutBundleManifest:
            raise TypeError("value must be CocoLayoutBundleManifest")
        return {
            "schema_version": value.CONTRACT_VERSION,
            "id": value.manifest_id,
            "profile_id": value.profile_id,
            "members": [
                {
                    "name": member.name.value,
                    "document_id": member.document_id,
                    "sha256": member.sha256,
                    "byte_length": member.byte_length,
                    "media_type": member.media_type,
                }
                for member in value.members
            ],
        }

    def from_json_value(self, value: JsonValue) -> CocoLayoutBundleManifest:
        root = CocoLayoutJsonValue.require_object(
            value,
            field="manifest",
            expected_fields=self.ROOT_FIELDS,
        )
        version = CocoLayoutJsonValue.require_string(
            root["schema_version"], field="schema_version"
        )
        if version != CocoLayoutBundleManifest.CONTRACT_VERSION:
            raise ValueError("unsupported COCO bundle manifest version")
        members = CocoLayoutBundleMemberInventory(
            *(
                self.member_from_json_value(item)
                for item in CocoLayoutJsonValue.require_array(
                    root["members"], field="members"
                )
            )
        )
        manifest = CocoLayoutBundleManifest(
            profile_id=CocoLayoutJsonValue.require_string(
                root["profile_id"], field="profile_id"
            ),
            members=members,
        )
        manifest_id = CocoLayoutJsonValue.require_string(root["id"], field="id")
        if manifest_id != manifest.manifest_id:
            raise ValueError("COCO bundle manifest identity is inconsistent")
        return manifest

    @classmethod
    def member_from_json_value(cls, value: JsonValue) -> CocoLayoutBundleMember:
        """Reconstruct one exact non-manifest member reference."""
        item = CocoLayoutJsonValue.require_object(
            value,
            field="manifest member",
            expected_fields=cls.MEMBER_FIELDS,
        )
        name_value = CocoLayoutJsonValue.require_string(
            item["name"], field="manifest member.name"
        )
        try:
            name = CocoLayoutBundleMemberName(name_value)
        except ValueError as error:
            raise ValueError("unknown COCO bundle member name") from error
        return CocoLayoutBundleMember(
            name=name,
            document_id=CocoLayoutJsonValue.require_string(
                item["document_id"], field="manifest member.document_id"
            ),
            sha256=SHA256Hash(
                CocoLayoutJsonValue.require_string(
                    item["sha256"], field="manifest member.sha256"
                )
            ),
            byte_length=CocoLayoutJsonValue.require_integer(
                item["byte_length"], field="manifest member.byte_length"
            ),
            media_type=CocoLayoutJsonValue.require_string(
                item["media_type"], field="manifest member.media_type"
            ),
        )
