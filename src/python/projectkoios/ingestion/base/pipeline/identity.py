"""Stable identity of one ingestion pipeline implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.identity import AbstractIdentity
from projectkoios.ingestion.identity import stable_id


@dataclass(frozen=True, slots=True)
class PipelineIdentity(AbstractIdentity):
    """Bind a pipeline to its contracts and ordered stage identities."""

    CONTRACT_NAME: ClassVar[str] = "pipeline-identity"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    pipeline_id: str
    name: str
    version: str
    request_contract: str
    configuration_contract: str
    result_contract: str
    stage_actionizer_ids: tuple[str, ...]
    has_external_effects: bool
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        name: str,
        version: str,
        request_contract: str,
        configuration_contract: str,
        result_contract: str,
        stage_actionizer_ids: tuple[str, ...],
        has_external_effects: bool,
    ) -> PipelineIdentity:
        """Create one identity from complete ordered stage declarations."""
        parts = (
            name,
            version,
            request_contract,
            configuration_contract,
            result_contract,
            stage_actionizer_ids,
            has_external_effects,
        )
        return cls(
            pipeline_id=stable_id(
                "pipeline-identity",
                cls.CONTRACT_VERSION,
                parts,
            ),
            name=name,
            version=version,
            request_contract=request_contract,
            configuration_contract=configuration_contract,
            result_contract=result_contract,
            stage_actionizer_ids=stage_actionizer_ids,
            has_external_effects=has_external_effects,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported pipeline-identity contract")
        text = (
            self.name,
            self.version,
            self.request_contract,
            self.configuration_contract,
            self.result_contract,
        )
        if any(type(value) is not str or not value for value in text):
            raise ValueError("pipeline identity is incomplete")
        if (
            not isinstance(self.stage_actionizer_ids, tuple)
            or not self.stage_actionizer_ids
            or any(
                type(value) is not str or not value
                for value in self.stage_actionizer_ids
            )
        ):
            raise ValueError("pipeline stage identities are invalid")
        if type(self.has_external_effects) is not bool:
            raise TypeError("pipeline effect declaration must be boolean")
        parts = (
            *text,
            self.stage_actionizer_ids,
            self.has_external_effects,
        )
        expected = stable_id(
            "pipeline-identity",
            self.CONTRACT_VERSION,
            parts,
        )
        if self.pipeline_id != expected:
            raise ValueError("pipeline identity is inconsistent")
