"""Frozen identity for a layout-region proposal source."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation
from projectkoios.ingestion.sha256.hash import SHA256Hash


@dataclass(frozen=True, slots=True)
class LayoutRegionProposalSource(AbstractImmutableDataObject):
    """Identify one exact detector, resource, and inference configuration."""

    CONTRACT_NAME: ClassVar[str] = "layout-region-proposal-source"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    proposal_source_id: str
    detector_name: str
    detector_version: str
    resource_identity: str
    resource_sha256: SHA256Hash | None
    configuration_id: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        detector_name: str,
        detector_version: str,
        resource_identity: str,
        resource_sha256: str | None,
        configuration_id: str,
    ) -> LayoutRegionProposalSource:
        """Create a stable proposal-source identity."""
        detector = LayoutValueValidation.require_text(
            "detector_name", detector_name
        )
        detector_release = LayoutValueValidation.require_text(
            "detector_version", detector_version
        )
        resource = LayoutValueValidation.require_text(
            "resource_identity", resource_identity
        )
        configuration = LayoutValueValidation.require_text(
            "configuration_id", configuration_id
        )
        digest = (
            None if resource_sha256 is None else SHA256Hash(resource_sha256)
        )
        source_id = stable_id(
            cls.CONTRACT_NAME,
            cls.CONTRACT_VERSION,
            detector,
            detector_release,
            resource,
            digest,
            configuration,
        )
        return cls(
            proposal_source_id=source_id,
            detector_name=detector,
            detector_version=detector_release,
            resource_identity=resource,
            resource_sha256=digest,
            configuration_id=configuration,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported layout proposal source contract")
        LayoutValueValidation.require_text("detector_name", self.detector_name)
        LayoutValueValidation.require_text(
            "detector_version", self.detector_version
        )
        LayoutValueValidation.require_text(
            "resource_identity", self.resource_identity
        )
        digest = (
            None
            if self.resource_sha256 is None
            else SHA256Hash(self.resource_sha256)
        )
        object.__setattr__(self, "resource_sha256", digest)
        LayoutValueValidation.require_text(
            "configuration_id", self.configuration_id
        )
        expected = stable_id(
            self.CONTRACT_NAME,
            self.CONTRACT_VERSION,
            self.detector_name,
            self.detector_version,
            self.resource_identity,
            digest,
            self.configuration_id,
        )
        if self.proposal_source_id != expected:
            raise ValueError("layout proposal source ID is inconsistent")
