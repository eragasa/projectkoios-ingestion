from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import ClassVar, cast

import pytest
from projectkoios.ingestion.base.actionizer.configurable import (
    ConfigurableDataObjectActionizer,
)
from projectkoios.ingestion.base.projector.configuration import (
    AbstractProjectionConfiguration,
)
from projectkoios.ingestion.base.projector.error import ProjectionContractError
from projectkoios.ingestion.base.projector.identity import ProjectorIdentity
from projectkoios.ingestion.base.projector.identity_error import (
    ProjectionIdentityError,
)
from projectkoios.ingestion.base.projector.payload_error import (
    ProjectionPayloadError,
)
from projectkoios.ingestion.base.projector.projector import Projector
from projectkoios.ingestion.base.projector.request import ProjectionRequest
from projectkoios.ingestion.base.projector.source import (
    AbstractProjectionSource,
)
from projectkoios.ingestion.base.projector.value import AbstractProjectionValue
from projectkoios.ingestion.identity import stable_id


@dataclass(frozen=True, slots=True)
class TextEvidence(AbstractProjectionSource):
    CONTRACT_NAME: ClassVar[str] = "text-evidence"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    evidence_id: str
    canonical_sha256: str
    text: str

    @classmethod
    def create(cls, text: str) -> TextEvidence:
        digest = hashlib.sha256(text.encode()).hexdigest()
        return cls(
            evidence_id=stable_id(
                "text-evidence", cls.CONTRACT_VERSION, digest
            ),
            canonical_sha256=digest,
            text=text,
        )


@dataclass(frozen=True, slots=True)
class TextProjectionConfiguration(AbstractProjectionConfiguration):
    CONTRACT_NAME: ClassVar[str] = "text-projection-configuration"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    configuration_id: str
    separator: str

    @classmethod
    def create(cls, separator: str) -> TextProjectionConfiguration:
        return cls(
            configuration_id=stable_id(
                "text-projection-configuration",
                cls.CONTRACT_VERSION,
                separator,
            ),
            separator=separator,
        )


@dataclass(frozen=True, slots=True)
class TextProjection(AbstractProjectionValue):
    CONTRACT_NAME: ClassVar[str] = "text-projection"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    projection_id: str
    source_evidence_ids: tuple[str, ...]
    schema_id: str
    canonical_sha256: str
    text: str

    @classmethod
    def create(
        cls,
        *,
        source_evidence_ids: tuple[str, ...],
        schema_id: str,
        text: str,
    ) -> TextProjection:
        digest = hashlib.sha256(text.encode()).hexdigest()
        return cls(
            projection_id=stable_id(
                "text-projection",
                cls.CONTRACT_VERSION,
                source_evidence_ids,
                schema_id,
                digest,
            ),
            source_evidence_ids=source_evidence_ids,
            schema_id=schema_id,
            canonical_sha256=digest,
            text=text,
        )


class TextProjector(
    Projector[
        TextEvidence,
        TextProjectionConfiguration,
        TextProjection,
    ]
):
    __slots__ = ()

    source_type = TextEvidence
    configuration_type = TextProjectionConfiguration
    projection_type = TextProjection
    identity = ProjectorIdentity.create(
        name="text-projector",
        version="1",
        source_contract=TextEvidence.CONTRACT_NAME,
        configuration_contract=TextProjectionConfiguration.CONTRACT_NAME,
        projection_contract=TextProjection.CONTRACT_NAME,
        schema_id="text-read-model-v1",
    )

    def project(
        self,
        *,
        sources: tuple[TextEvidence, ...],
        configuration: TextProjectionConfiguration,
    ) -> TextProjection:
        return TextProjection.create(
            source_evidence_ids=tuple(source.evidence_id for source in sources),
            schema_id=self.identity.schema_id,
            text=configuration.separator.join(
                source.text for source in sources
            ),
        )


def request() -> ProjectionRequest[
    TextEvidence,
    TextProjectionConfiguration,
]:
    sources = tuple(
        sorted(
            (TextEvidence.create("beta"), TextEvidence.create("alpha")),
            key=lambda source: source.evidence_id,
        )
    )
    return ProjectionRequest.create(
        sources=sources,
        configuration=TextProjectionConfiguration.create("\n"),
    )


def test__projector__inherits_configurable_actionizer() -> None:
    assert issubclass(Projector, ConfigurableDataObjectActionizer)


def test__projector__specialized_errors_retain_contract_boundary() -> None:
    assert issubclass(ProjectionIdentityError, ProjectionContractError)
    assert issubclass(ProjectionPayloadError, ProjectionContractError)
    assert not issubclass(ProjectionPayloadError, ProjectionIdentityError)


def test__projector__uses_one_fixed_deterministic_pattern() -> None:
    projector = TextProjector()
    projection_request = request()

    first = projector.action(request=projection_request)
    second = projector.action(request=projection_request)

    assert first == second
    assert first.request_id == projection_request.request_id
    assert first.projector == projector.identity
    assert first.projection.source_evidence_ids == tuple(
        source.evidence_id for source in projection_request.sources
    )
    assert projector.has_external_effects is False
    assert projector.authority_requirements == ()
    with pytest.raises(AttributeError):
        projector.state = "forbidden"  # type: ignore[attr-defined]


def test__projection_request__rejects_noncanonical_sources() -> None:
    sources = (TextEvidence.create("beta"), TextEvidence.create("alpha"))
    assert sources != tuple(
        sorted(sources, key=lambda source: source.evidence_id)
    )

    with pytest.raises(ValueError, match="not canonical"):
        ProjectionRequest.create(
            sources=sources,
            configuration=TextProjectionConfiguration.create("\n"),
        )


def test__projection_request__rejects_any_object_source() -> None:
    with pytest.raises(TypeError, match="sources are invalid"):
        ProjectionRequest.create(
            sources=cast(tuple[TextEvidence, ...], (object(),)),
            configuration=TextProjectionConfiguration.create("\n"),
        )


def test__projector__rejects_wrong_projection_contract() -> None:
    class WrongProjectionProjector(TextProjector):
        __slots__ = ()

        def project(
            self,
            *,
            sources: tuple[TextEvidence, ...],
            configuration: TextProjectionConfiguration,
        ) -> TextProjection:
            return cast(TextProjection, configuration)

    with pytest.raises(
        ProjectionContractError, match="output contract differs"
    ):
        WrongProjectionProjector().action(request=request())


def test__projector__separates_identity_contract_failure() -> None:
    class WrongIdentityProjector(TextProjector):
        __slots__ = ()
        identity = ProjectorIdentity.create(
            name="wrong-identity-projector",
            version="1",
            source_contract=TextEvidence.CONTRACT_NAME,
            configuration_contract=(TextProjectionConfiguration.CONTRACT_NAME),
            projection_contract="another-projection",
            schema_id="text-read-model-v1",
        )

    with pytest.raises(
        ProjectionIdentityError,
        match="identity contracts differ",
    ):
        WrongIdentityProjector().action(request=request())


def test__projector__rejects_effectful_declaration() -> None:
    with pytest.raises(TypeError, match="external effects"):

        class EffectfulProjector(TextProjector):
            __slots__ = ()
            has_external_effects = True


def test__projector__rejects_action_override() -> None:
    with pytest.raises(TypeError, match="fixed action"):

        class OverrideProjector(TextProjector):
            __slots__ = ()

            def action(self, *, request: object) -> object:
                return request


def test__projector__rejects_instance_initialization() -> None:
    with pytest.raises(TypeError, match="instance initialization"):

        class StatefulProjector(TextProjector):
            __slots__ = ()

            def __init__(self) -> None:
                pass


def test__projector__rejects_another_action_kind() -> None:
    with pytest.raises(TypeError, match="action kind"):

        class ProcessorProjector(TextProjector):
            __slots__ = ()
            action_kind = "processor"
