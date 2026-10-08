"""Exact backend-neutral reading-evidence materialization targets."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.materializer.target import (
    AbstractMaterializationTarget,
)
from projectkoios.ingestion.identity import stable_id

_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,255}")
_SCHEMA_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}")


@dataclass(frozen=True, slots=True)
class ReadingEvidenceMaterializationTarget(AbstractMaterializationTarget):
    """Identify one exact deployment, environment, store, and schema."""

    CONTRACT_NAME: ClassVar[str] = "reading-evidence-materialization-target"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    target_id: str
    deployment_id: str
    environment: str
    store_name: str
    schema_id: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        deployment_id: str,
        environment: str,
        store_name: str,
        schema_id: str,
    ) -> ReadingEvidenceMaterializationTarget:
        """Create one target from every exact resource dimension."""
        values = (
            deployment_id,
            environment,
            store_name,
            schema_id,
        )
        return cls(
            target_id=stable_id(
                "reading-evidence-materialization-target",
                cls.CONTRACT_VERSION,
                values,
            ),
            deployment_id=deployment_id,
            environment=environment,
            store_name=store_name,
            schema_id=schema_id,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported materialization target")
        values = (
            self.deployment_id,
            self.environment,
            self.store_name,
            self.schema_id,
        )
        names = (
            self.deployment_id,
            self.environment,
            self.store_name,
        )
        if any(
            type(value) is not str or not _NAME.fullmatch(value)
            for value in names
        ) or (
            type(self.schema_id) is not str
            or not _SCHEMA_ID.fullmatch(self.schema_id)
        ):
            raise ValueError("materialization target is incomplete")
        expected = stable_id(
            "reading-evidence-materialization-target",
            self.CONTRACT_VERSION,
            values,
        )
        if self.target_id != expected:
            raise ValueError("materialization target ID is inconsistent")
