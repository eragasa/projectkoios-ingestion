"""Exact COCO layout proposal-adaptation configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.actionizer.configuration import (
    AbstractActionConfiguration,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.limits.definition import (
    MAX_COCO_LAYOUT_DETECTIONS,
)
from projectkoios.ingestion.integrations.coco.layout.limits.error import (
    CocoLayoutLimitError,
)
from projectkoios.ingestion.integrations.coco.layout.profile import (
    CocoLayoutProfile,
)
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation
from projectkoios.ingestion.sha256.hash import SHA256Hash


@dataclass(frozen=True, slots=True)
class CocoLayoutProposalConfiguration(AbstractActionConfiguration):
    """Bind one COCO profile, detector/runtime resource, and hard bound."""

    CONTRACT_NAME: ClassVar[str] = "coco-layout-proposal-configuration"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    profile: CocoLayoutProfile
    detector_name: str
    detector_version: str
    runtime_name: str
    runtime_version: str
    resource_identity: str
    resource_sha256: SHA256Hash
    max_detections: int = MAX_COCO_LAYOUT_DETECTIONS
    configuration_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.profile) is not CocoLayoutProfile:
            raise TypeError("profile must be CocoLayoutProfile")
        values = tuple(
            LayoutValueValidation.require_text(name, getattr(self, name))
            for name in (
                "detector_name",
                "detector_version",
                "runtime_name",
                "runtime_version",
                "resource_identity",
            )
        )
        digest = SHA256Hash(self.resource_sha256)
        object.__setattr__(self, "resource_sha256", digest)
        maximum = LayoutValueValidation.require_positive_integer(
            "max_detections", self.max_detections
        )
        if maximum > MAX_COCO_LAYOUT_DETECTIONS:
            raise CocoLayoutLimitError(
                "max_detections exceeds the implementation limit"
            )
        object.__setattr__(
            self,
            "configuration_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                self.profile.profile_id,
                values,
                digest,
                maximum,
            ),
        )
