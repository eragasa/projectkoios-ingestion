"""Stable identity of one ingestion projector implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.identity import AbstractIdentity
from projectkoios.ingestion.identity import stable_id


@dataclass(frozen=True, slots=True)
class ProjectorIdentity(AbstractIdentity):
    """Bind implementation and input/output/schema contracts."""

    CONTRACT_NAME: ClassVar[str] = "projector-identity"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    projector_id: str
    name: str
    version: str
    source_contract: str
    configuration_contract: str
    projection_contract: str
    schema_id: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        name: str,
        version: str,
        source_contract: str,
        configuration_contract: str,
        projection_contract: str,
        schema_id: str,
    ) -> ProjectorIdentity:
        parts = (
            name,
            version,
            source_contract,
            configuration_contract,
            projection_contract,
            schema_id,
        )
        return cls(
            projector_id=stable_id(
                "projector-identity", cls.CONTRACT_VERSION, parts
            ),
            name=name,
            version=version,
            source_contract=source_contract,
            configuration_contract=configuration_contract,
            projection_contract=projection_contract,
            schema_id=schema_id,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported projector-identity contract")
        parts = (
            self.name,
            self.version,
            self.source_contract,
            self.configuration_contract,
            self.projection_contract,
            self.schema_id,
        )
        if any(type(value) is not str or not value for value in parts):
            raise ValueError("projector identity is incomplete")
        expected = stable_id("projector-identity", self.CONTRACT_VERSION, parts)
        if self.projector_id != expected:
            raise ValueError("projector identity is inconsistent")
