from dataclasses import FrozenInstanceError, replace
from unittest.mock import Mock

import pytest
from projectkoios.ingestion.artifact.managed.inventory import (
    ManagedArtifactReferenceInventory,
)
from projectkoios.ingestion.artifact.managed.limits.error import (
    ManagedArtifactLimitError,
)
from projectkoios.ingestion.artifact.managed.media.type import (
    ManagedArtifactMediaType,
)
from projectkoios.ingestion.artifact.managed.reference import (
    ManagedArtifactReference,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter


def test__managed_artifact_reference__is_exact_and_locator_free() -> None:
    reference = ManagedArtifactReference(
        sha256="a" * 64,
        byte_length=128,
        media_type=ManagedArtifactMediaType.APPLICATION_PDF,
    )

    assert reference.artifact_id.startswith("managed-artifact:sha256:")
    assert reference.sha256 == "a" * 64
    assert reference.byte_length == 128
    assert not hasattr(reference, "path")
    assert not hasattr(reference, "locator")
    assert not hasattr(reference, "url")


def test__managed_artifact_reference__validates_before_hashing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fingerprint = Mock(side_effect=AssertionError("hashing must not run"))
    monkeypatch.setattr(SHA256Fingerprinter, "fingerprint", fingerprint)

    with pytest.raises(ManagedArtifactLimitError):
        ManagedArtifactReference(
            sha256="a" * 64,
            byte_length=4_000_000_001,
            media_type=ManagedArtifactMediaType.APPLICATION_PDF,
        )

    fingerprint.assert_not_called()


def test__managed_artifact_reference__recomputes_identity_on_change() -> None:
    reference = ManagedArtifactReference(
        sha256="a" * 64,
        byte_length=128,
        media_type=ManagedArtifactMediaType.IMAGE_PNG,
    )

    changed = replace(reference, byte_length=129)

    assert changed.artifact_id != reference.artifact_id


def test__managed_artifact_reference_inventory__requires_canonical_order() -> (
    None
):
    first = ManagedArtifactReference(
        sha256="a" * 64,
        byte_length=10,
        media_type=ManagedArtifactMediaType.IMAGE_PNG,
    )
    second = ManagedArtifactReference(
        sha256="b" * 64,
        byte_length=20,
        media_type=ManagedArtifactMediaType.IMAGE_PNG,
    )
    ordered = sorted((first, second), key=lambda value: value.artifact_id)

    inventory = ManagedArtifactReferenceInventory(*ordered)

    assert len(inventory) == 2
    assert inventory.aggregate_byte_length == 30
    assert inventory.require(first.artifact_id) == first
    with pytest.raises(ValueError, match="sorted"):
        ManagedArtifactReferenceInventory(*reversed(ordered))


def test__managed_artifact_reference__is_immutable() -> None:
    reference = ManagedArtifactReference(
        sha256="a" * 64,
        byte_length=128,
        media_type=ManagedArtifactMediaType.IMAGE_PNG,
    )

    with pytest.raises(FrozenInstanceError):
        reference.byte_length = 1  # type: ignore[misc]
