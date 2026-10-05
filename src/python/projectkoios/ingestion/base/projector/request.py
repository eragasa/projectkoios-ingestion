"""Fixed request envelope for every ingestion projector."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.base.projector.configuration import (
    AbstractProjectionConfiguration,
)
from projectkoios.ingestion.base.projector.source import (
    AbstractProjectionSource,
)
from projectkoios.ingestion.identity import stable_id

_SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class ProjectionRequest[
    SourceT: AbstractProjectionSource,
    ConfigurationT: AbstractProjectionConfiguration,
](AbstractImmutableDataObject, DataObjectActionRequest):
    """Carry canonical evidence and complete deterministic configuration.

    Parameters
    ----------
    request_id
        Stable identity over source identities, digests, and configuration.
    sources
        Nonempty, canonically ordered, identity-unique source evidence.
    configuration
        Complete immutable deterministic configuration.
    contract_version
        Version of this fixed request envelope.
    """

    CONTRACT_NAME: ClassVar[str] = "projection-request"
    CONTRACT_VERSION: ClassVar[str] = "1.0"
    MAXIMUM_SOURCES: ClassVar[int] = 1_000_000

    request_id: str
    sources: tuple[SourceT, ...]
    configuration: ConfigurationT
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        sources: tuple[SourceT, ...],
        configuration: ConfigurationT,
    ) -> ProjectionRequest[SourceT, ConfigurationT]:
        """Create the fixed request envelope.

        Parameters
        ----------
        sources
            Canonically ordered immutable source evidence.
        configuration
            Complete immutable deterministic configuration.

        Returns
        -------
        ProjectionRequest[SourceT, ConfigurationT]
            Request with a stable identity over exact inputs.

        Raises
        ------
        TypeError
            If sources or configuration do not implement nominal contracts.
        ValueError
            If sources are empty, unordered, duplicate, invalid, or unbounded.
        """
        if not isinstance(sources, tuple) or any(
            not isinstance(source, AbstractProjectionSource)
            for source in sources
        ):
            raise TypeError("projection sources are invalid")
        if not isinstance(configuration, AbstractProjectionConfiguration):
            raise TypeError("projection configuration is invalid")
        source_parts = tuple(
            (source.evidence_id, source.canonical_sha256) for source in sources
        )
        return cls(
            request_id=stable_id(
                "projection-request",
                cls.CONTRACT_VERSION,
                source_parts,
                configuration.configuration_id,
            ),
            sources=sources,
            configuration=configuration,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported projection-request contract")
        if not isinstance(self.sources, tuple) or any(
            not isinstance(source, AbstractProjectionSource)
            for source in self.sources
        ):
            raise TypeError("projection sources are invalid")
        if not self.sources or len(self.sources) > self.MAXIMUM_SOURCES:
            raise ValueError("projection source count is out of bounds")
        source_parts = tuple(
            (source.evidence_id, source.canonical_sha256)
            for source in self.sources
        )
        if any(
            type(evidence_id) is not str
            or not evidence_id
            or type(digest) is not str
            or not _SHA256.fullmatch(digest)
            for evidence_id, digest in source_parts
        ):
            raise ValueError("projection source identity is invalid")
        if source_parts != tuple(sorted(source_parts)):
            raise ValueError("projection sources are not canonical")
        if len({evidence_id for evidence_id, _ in source_parts}) != len(
            source_parts
        ):
            raise ValueError("projection source identities must be unique")
        if not isinstance(
            self.configuration, AbstractProjectionConfiguration
        ) or (
            type(self.configuration.configuration_id) is not str
            or not self.configuration.configuration_id
        ):
            raise TypeError("projection configuration is invalid")
        expected = stable_id(
            "projection-request",
            self.CONTRACT_VERSION,
            source_parts,
            self.configuration.configuration_id,
        )
        if self.request_id != expected:
            raise ValueError("projection request ID is inconsistent")
