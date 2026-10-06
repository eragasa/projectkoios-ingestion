"""Stable identity of one ingestion materializer implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.identity import AbstractIdentity
from projectkoios.ingestion.identity import stable_id


@dataclass(frozen=True, slots=True)
class MaterializerIdentity(AbstractIdentity):
    """Bind an effectful implementation to all declared contracts.

    Parameters
    ----------
    materializer_id
        Stable identity over every remaining field.
    name
        Stable implementation name.
    version
        Explicit implementation version.
    projection_contract
        Contract name required for input projection values.
    target_contract
        Contract name required for explicit target identities.
    configuration_contract
        Contract name required for write configuration.
    evidence_contract
        Contract name guaranteed for output evidence.
    schema_id
        Logical projection schema accepted by the implementation.
    authority_requirement
        Stable permission name required by the owning provider action.
    contract_version
        Version of this identity envelope.
    """

    CONTRACT_NAME: ClassVar[str] = "materializer-identity"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    materializer_id: str
    name: str
    version: str
    projection_contract: str
    target_contract: str
    configuration_contract: str
    evidence_contract: str
    schema_id: str
    authority_requirement: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        name: str,
        version: str,
        projection_contract: str,
        target_contract: str,
        configuration_contract: str,
        evidence_contract: str,
        schema_id: str,
        authority_requirement: str,
    ) -> MaterializerIdentity:
        """Create one identity from complete contract declarations.

        Returns
        -------
        MaterializerIdentity
            Immutable identity binding implementation, schema, and authority.
        """
        parts = (
            name,
            version,
            projection_contract,
            target_contract,
            configuration_contract,
            evidence_contract,
            schema_id,
            authority_requirement,
        )
        return cls(
            materializer_id=stable_id(
                "materializer-identity",
                cls.CONTRACT_VERSION,
                parts,
            ),
            name=name,
            version=version,
            projection_contract=projection_contract,
            target_contract=target_contract,
            configuration_contract=configuration_contract,
            evidence_contract=evidence_contract,
            schema_id=schema_id,
            authority_requirement=authority_requirement,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported materializer-identity contract")
        parts = (
            self.name,
            self.version,
            self.projection_contract,
            self.target_contract,
            self.configuration_contract,
            self.evidence_contract,
            self.schema_id,
            self.authority_requirement,
        )
        if any(type(value) is not str or not value for value in parts):
            raise ValueError("materializer identity is incomplete")
        expected = stable_id(
            "materializer-identity",
            self.CONTRACT_VERSION,
            parts,
        )
        if self.materializer_id != expected:
            raise ValueError("materializer identity is inconsistent")
