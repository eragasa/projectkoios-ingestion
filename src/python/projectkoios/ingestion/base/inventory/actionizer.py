"""Fixed read-only inventory execution pattern."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import final

from projectkoios.ingestion.base.actionizer.configurable import (
    ConfigurableDataObjectActionizer,
)
from projectkoios.ingestion.base.inventory.configuration import (
    AbstractInventoryConfiguration,
)
from projectkoios.ingestion.base.inventory.error import InventoryContractError
from projectkoios.ingestion.base.inventory.evidence import (
    AbstractInventoryEvidence,
)
from projectkoios.ingestion.base.inventory.identity.error import (
    InventoryIdentityError,
)
from projectkoios.ingestion.base.inventory.identity.model import (
    InventoryIdentity,
)
from projectkoios.ingestion.base.inventory.request import InventoryRequest
from projectkoios.ingestion.base.inventory.result import InventoryResult
from projectkoios.ingestion.base.inventory.target import AbstractInventoryTarget


class Inventory[
    TargetT: AbstractInventoryTarget,
    ConfigurationT: AbstractInventoryConfiguration,
    EvidenceT: AbstractInventoryEvidence,
](
    ConfigurableDataObjectActionizer[
        ConfigurationT,
        InventoryRequest[TargetT, ConfigurationT],
        InventoryResult[EvidenceT],
    ],
    ABC,
):
    """Observe one explicit external target without mutating it."""

    __slots__ = ()

    action_kind = "inventory"
    has_external_reads = True
    has_external_writes = False

    identity: InventoryIdentity
    target_type: type[TargetT]
    configuration_type: type[ConfigurationT]
    evidence_type: type[EvidenceT]
    authority_requirement: str

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if "action" in cls.__dict__:
            raise TypeError("inventories cannot override the fixed action")
        if "__slots__" not in cls.__dict__:
            raise TypeError("inventories must declare explicit instance slots")
        if cls.__dict__.get("action_kind", "inventory") != "inventory":
            raise TypeError("inventories cannot change their action kind")
        if cls.__dict__.get("has_external_writes", False) is not False:
            raise TypeError("inventories cannot declare external writes")

    @final
    def action(
        self,
        *,
        request: InventoryRequest[TargetT, ConfigurationT],
    ) -> InventoryResult[EvidenceT]:
        """Validate, observe, and bind one inventory result."""
        if not isinstance(request, InventoryRequest):
            raise TypeError("request must be an InventoryRequest")
        if type(request.target) is not self.target_type:
            raise InventoryContractError("inventory target contract differs")
        try:
            configuration = self._require_configuration(request=request)
        except TypeError as error:
            raise InventoryContractError(
                "inventory configuration contract differs"
            ) from error
        self._validate_identity()
        self._validate_request_identity(request=request)
        evidence = self.observe(
            target=request.target,
            configuration=configuration,
            authority_id=request.authority_id,
        )
        if type(evidence) is not self.evidence_type:
            raise InventoryContractError("inventory evidence contract differs")
        if (
            evidence.target_id != request.target.target_id
            or evidence.configuration_id != configuration.configuration_id
            or evidence.authority_id != request.authority_id
        ):
            raise InventoryIdentityError(
                "inventory evidence provenance differs"
            )
        self._validate_evidence_identity(
            request=request,
            evidence=evidence,
        )
        return InventoryResult.create(
            request_id=request.request_id,
            idempotency_key=request.idempotency_key,
            inventory=self.identity,
            evidence=evidence,
        )

    @abstractmethod
    def observe(
        self,
        *,
        target: TargetT,
        configuration: ConfigurationT,
        authority_id: str,
    ) -> EvidenceT:
        """Observe one target without changing target state."""

    def _validate_request_identity(
        self,
        *,
        request: InventoryRequest[TargetT, ConfigurationT],
    ) -> None:
        """Validate specialization-specific request identities."""

    def _validate_evidence_identity(
        self,
        *,
        request: InventoryRequest[TargetT, ConfigurationT],
        evidence: EvidenceT,
    ) -> None:
        """Validate specialization-specific evidence identities."""

    def _validate_identity(self) -> None:
        if not isinstance(self.identity, InventoryIdentity):
            raise InventoryIdentityError("inventory identity is invalid")
        expected = (
            self.target_type.CONTRACT_NAME,
            self.configuration_type.CONTRACT_NAME,
            self.evidence_type.CONTRACT_NAME,
            self.authority_requirement,
        )
        actual = (
            self.identity.target_contract,
            self.identity.configuration_contract,
            self.identity.evidence_contract,
            self.identity.authority_requirement,
        )
        if expected != actual:
            raise InventoryIdentityError("inventory identity contracts differ")
