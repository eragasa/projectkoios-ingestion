"""Complete deterministic extraction read-model configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.projector.configuration import (
    AbstractProjectionConfiguration,
)
from projectkoios.ingestion.identity import stable_id


@dataclass(frozen=True, slots=True)
class ExtractionProjectionConfiguration(AbstractProjectionConfiguration):
    """Contain every deterministic extraction-projection choice.

    Parameters
    ----------
    configuration_id
        Stable identity over all configuration fields.
    schema_id
        Logical read-model schema consumed by materializers.
    identity_version
        Version included in every derived page, block, and warning identity.
    page_identity_namespace
        Vendor-neutral namespace for projected page identities.
    block_identity_namespace
        Vendor-neutral namespace for projected block identities.
    warning_identity_namespace
        Vendor-neutral namespace for projected warning identities.
    completion_state
        State written only to the root completion document.
    contract_version
        Version of this configuration contract.

    Notes
    -----
    Physical database names and connection targets are intentionally absent.
    They belong to an effectful materializer, not the pure projection.
    """

    CONTRACT_NAME: ClassVar[str] = "extraction-projection-configuration"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    configuration_id: str
    schema_id: str
    identity_version: str
    page_identity_namespace: str
    block_identity_namespace: str
    warning_identity_namespace: str
    completion_state: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def v1(cls) -> ExtractionProjectionConfiguration:
        """Return the complete version-one extraction schema configuration.

        Returns
        -------
        ExtractionProjectionConfiguration
            Frozen configuration for ``extraction-read-model-v1``.
        """
        values = (
            "extraction-read-model-v1",
            "1.0",
            "extraction-projection-page",
            "extraction-projection-block",
            "extraction-projection-warning",
            "complete",
        )
        return cls(
            configuration_id=stable_id(
                "extraction-projection-configuration",
                cls.CONTRACT_VERSION,
                values,
            ),
            schema_id=values[0],
            identity_version=values[1],
            page_identity_namespace=values[2],
            block_identity_namespace=values[3],
            warning_identity_namespace=values[4],
            completion_state=values[5],
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported extraction projection configuration")
        values = (
            self.schema_id,
            self.identity_version,
            self.page_identity_namespace,
            self.block_identity_namespace,
            self.warning_identity_namespace,
            self.completion_state,
        )
        if any(type(value) is not str or not value for value in values):
            raise ValueError(
                "extraction projection configuration is incomplete"
            )
        for namespace in (
            self.page_identity_namespace,
            self.block_identity_namespace,
            self.warning_identity_namespace,
        ):
            if ":" in namespace:
                raise ValueError("projection identity namespace is invalid")
        expected = stable_id(
            "extraction-projection-configuration",
            self.CONTRACT_VERSION,
            values,
        )
        if self.configuration_id != expected:
            raise ValueError("projection configuration ID is inconsistent")
