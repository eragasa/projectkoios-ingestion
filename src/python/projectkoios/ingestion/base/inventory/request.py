"""Fixed request envelope for inventory observations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.actionizer.request import (
    ConfigurableDataObjectActionRequest,
)
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.base.inventory.configuration import (
    AbstractInventoryConfiguration,
)
from projectkoios.ingestion.base.inventory.target import AbstractInventoryTarget
from projectkoios.ingestion.identity import stable_id


@dataclass(frozen=True, slots=True)
class InventoryRequest[
    TargetT: AbstractInventoryTarget,
    ConfigurationT: AbstractInventoryConfiguration,
](
    AbstractImmutableDataObject,
    ConfigurableDataObjectActionRequest[ConfigurationT],
):
    """Bind one target, observation configuration, and query authority."""

    CONTRACT_NAME: ClassVar[str] = "inventory-request"
    CONTRACT_VERSION: ClassVar[str] = "1.0"
    MAXIMUM_TEXT_LENGTH: ClassVar[int] = 4_096

    request_id: str
    idempotency_key: str
    target: TargetT
    configuration: ConfigurationT
    authority_id: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        target: TargetT,
        configuration: ConfigurationT,
        authority_id: str,
    ) -> InventoryRequest[TargetT, ConfigurationT]:
        """Create an authority-bound request and neutral observation key."""
        if not isinstance(target, AbstractInventoryTarget):
            raise TypeError("inventory target is invalid")
        if not isinstance(configuration, AbstractInventoryConfiguration):
            raise TypeError("inventory configuration is invalid")
        key = cls._idempotency(target=target, configuration=configuration)
        return cls(
            request_id=stable_id(
                "inventory-request",
                cls.CONTRACT_VERSION,
                key,
                authority_id,
            ),
            idempotency_key=key,
            target=target,
            configuration=configuration,
            authority_id=authority_id,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported inventory-request contract")
        if not isinstance(self.target, AbstractInventoryTarget):
            raise TypeError("inventory target is invalid")
        if not isinstance(self.configuration, AbstractInventoryConfiguration):
            raise TypeError("inventory configuration is invalid")
        for value in (
            self.target.target_id,
            self.configuration.configuration_id,
            self.authority_id,
        ):
            if (
                type(value) is not str
                or not value
                or len(value) > self.MAXIMUM_TEXT_LENGTH
            ):
                raise ValueError("inventory request identity is invalid")
        key = self._idempotency(
            target=self.target,
            configuration=self.configuration,
        )
        if self.idempotency_key != key:
            raise ValueError("inventory idempotency is inconsistent")
        expected = stable_id(
            "inventory-request",
            self.CONTRACT_VERSION,
            key,
            self.authority_id,
        )
        if self.request_id != expected:
            raise ValueError("inventory request ID is inconsistent")

    @classmethod
    def _idempotency(
        cls,
        *,
        target: AbstractInventoryTarget,
        configuration: AbstractInventoryConfiguration,
    ) -> str:
        return stable_id(
            "inventory-idempotency",
            cls.CONTRACT_VERSION,
            target.target_id,
            configuration.configuration_id,
        )
