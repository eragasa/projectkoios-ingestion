from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import pytest
from projectkoios.ingestion.base.actionizer.configurable import (
    ConfigurableDataObjectActionizer,
)
from projectkoios.ingestion.base.materializer.configuration import (
    AbstractMaterializationConfiguration,
)
from projectkoios.ingestion.base.materializer.evidence import (
    AbstractMaterializationEvidence,
)
from projectkoios.ingestion.base.materializer.identity.model import (
    MaterializerIdentity,
)
from projectkoios.ingestion.base.materializer.materializer import Materializer
from projectkoios.ingestion.base.materializer.request import (
    MaterializationRequest,
)
from projectkoios.ingestion.base.materializer.target import (
    AbstractMaterializationTarget,
)
from projectkoios.ingestion.base.projector.value import AbstractProjectionValue
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter


@dataclass(frozen=True, slots=True)
class FixtureProjection(AbstractProjectionValue):
    CONTRACT_NAME: ClassVar[str] = "fixture-projection"

    projection_id: str
    source_evidence_ids: tuple[str, ...]
    schema_id: str
    canonical_sha256: str
    text: str

    @classmethod
    def create(cls, text: str) -> FixtureProjection:
        digest = SHA256Fingerprinter.fingerprint(content=text.encode())
        return cls(
            projection_id=stable_id("fixture-projection", digest),
            source_evidence_ids=("fixture-evidence:one",),
            schema_id="fixture-schema-v1",
            canonical_sha256=digest,
            text=text,
        )


@dataclass(frozen=True, slots=True)
class FixtureTarget(AbstractMaterializationTarget):
    CONTRACT_NAME: ClassVar[str] = "fixture-target"

    target_id: str
    schema_id: str

    @classmethod
    def create(cls, name: str) -> FixtureTarget:
        return cls(
            target_id=stable_id("fixture-target", name),
            schema_id="fixture-schema-v1",
        )


@dataclass(frozen=True, slots=True)
class FixtureConfiguration(AbstractMaterializationConfiguration):
    CONTRACT_NAME: ClassVar[str] = "fixture-materialization-configuration"

    configuration_id: str
    schema_id: str

    @classmethod
    def create(cls) -> FixtureConfiguration:
        return cls(
            configuration_id=stable_id("fixture-configuration", "v1"),
            schema_id="fixture-schema-v1",
        )


@dataclass(frozen=True, slots=True)
class FixtureEvidence(AbstractMaterializationEvidence):
    CONTRACT_NAME: ClassVar[str] = "fixture-materialization-evidence"

    evidence_id: str
    projection_id: str
    target_id: str
    configuration_id: str
    authority_id: str
    canonical_sha256: str
    created: bool

    @classmethod
    def create(
        cls,
        *,
        projection_id: str,
        target_id: str,
        configuration_id: str,
        authority_id: str,
        created: bool,
    ) -> FixtureEvidence:
        digest = SHA256Fingerprinter.fingerprint(content=str(created).encode())
        return cls(
            evidence_id=stable_id(
                "fixture-materialization-evidence",
                projection_id,
                target_id,
                configuration_id,
                authority_id,
                created,
            ),
            projection_id=projection_id,
            target_id=target_id,
            configuration_id=configuration_id,
            authority_id=authority_id,
            canonical_sha256=digest,
            created=created,
        )


class RecordingMaterializer(
    Materializer[
        FixtureProjection,
        FixtureTarget,
        FixtureConfiguration,
        FixtureEvidence,
    ]
):
    __slots__ = ("written",)

    authority_requirement = "fixture_write"
    projection_type = FixtureProjection
    target_type = FixtureTarget
    configuration_type = FixtureConfiguration
    evidence_type = FixtureEvidence
    identity = MaterializerIdentity.create(
        name="recording-materializer",
        version="1",
        projection_contract=FixtureProjection.CONTRACT_NAME,
        target_contract=FixtureTarget.CONTRACT_NAME,
        configuration_contract=FixtureConfiguration.CONTRACT_NAME,
        evidence_contract=FixtureEvidence.CONTRACT_NAME,
        schema_id="fixture-schema-v1",
        authority_requirement=authority_requirement,
    )

    def __init__(self) -> None:
        self.written: set[tuple[str, str]] = set()

    def materialize(
        self,
        *,
        projection: FixtureProjection,
        target: FixtureTarget,
        configuration: FixtureConfiguration,
        authority_id: str,
    ) -> FixtureEvidence:
        key = (projection.projection_id, target.target_id)
        created = key not in self.written
        self.written.add(key)
        return FixtureEvidence.create(
            projection_id=projection.projection_id,
            target_id=target.target_id,
            configuration_id=configuration.configuration_id,
            authority_id=authority_id,
            created=created,
        )


def request() -> MaterializationRequest[
    FixtureProjection,
    FixtureTarget,
    FixtureConfiguration,
]:
    return MaterializationRequest.create(
        projection=FixtureProjection.create("exact projection"),
        target=FixtureTarget.create("development"),
        configuration=FixtureConfiguration.create(),
        authority_id="authority:fixture-write",
    )


def test__materializer__inherits_configurable_actionizer() -> None:
    assert issubclass(Materializer, ConfigurableDataObjectActionizer)


def test__materializer__binds_effectful_created_and_replay_evidence() -> None:
    materializer = RecordingMaterializer()
    materialization_request = request()

    created = materializer.action(request=materialization_request)
    replayed = materializer.action(request=materialization_request)

    assert created.request_id == materialization_request.request_id
    assert created.idempotency_key == replayed.idempotency_key
    assert created.evidence.created is True
    assert replayed.evidence.created is False
    assert created.result_id != replayed.result_id
    assert materializer.has_external_effects is True


def test__materialization_request__separates_authority_from_idempotency() -> (
    None
):
    first = request()
    second = MaterializationRequest.create(
        projection=first.projection,
        target=first.target,
        configuration=first.configuration,
        authority_id="authority:another-grant",
    )

    assert first.request_id != second.request_id
    assert first.idempotency_key == second.idempotency_key


def test__materializer__requires_explicit_slots() -> None:
    with pytest.raises(TypeError, match="explicit instance slots"):

        class HiddenStateMaterializer(RecordingMaterializer):
            pass


def test__materializer__cannot_override_fixed_action() -> None:
    with pytest.raises(TypeError, match="fixed action"):

        class OverrideMaterializer(RecordingMaterializer):
            __slots__ = ()

            def action(self, *, request: object) -> object:
                return request
