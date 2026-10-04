from dataclasses import replace
from types import SimpleNamespace

import pytest
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.transcription.artifact_inventory import (
    TranscriptionInputArtifactInventory,
)


def test__artifact_inventory__validates_identity_and_byte_accounting() -> None:
    identity_parts = (
        ("rendered-region:sha256:one",),
        ("embedded-figure-artifact:sha256:two",),
        11,
        13,
        17,
        41,
    )
    inventory = TranscriptionInputArtifactInventory(
        inventory_id=stable_id(
            "transcription-input-artifact-inventory", *identity_parts
        ),
        rendered_region_ids=identity_parts[0],
        embedded_artifact_ids=identity_parts[1],
        rendered_bytes=11,
        embedded_bytes=13,
        mask_bytes=17,
        total_bytes=41,
    )

    assert inventory.total_bytes == 41
    with pytest.raises(ValueError, match="byte total"):
        replace(inventory, total_bytes=40)
    with pytest.raises(ValueError, match="identity"):
        replace(inventory, inventory_id="forged")


def test__artifact_inventory__deduplicates_shared_rendered_evidence() -> None:
    shared_region = SimpleNamespace(region_id="shared-region", byte_length=23)
    equation_result = SimpleNamespace(
        candidates=(SimpleNamespace(rendered_region=shared_region),)
    )
    table_result = SimpleNamespace(
        structure_input=SimpleNamespace(
            detection_result=SimpleNamespace(
                candidates=(
                    SimpleNamespace(
                        regions=(
                            SimpleNamespace(rendered_region=shared_region),
                        )
                    ),
                )
            )
        )
    )
    figure_result = SimpleNamespace(
        detection_input=SimpleNamespace(page_evidence=()), candidates=()
    )

    inventory = TranscriptionInputArtifactInventory.derive(
        equation_result, table_result, figure_result
    )

    assert inventory.rendered_region_ids == ("shared-region",)
    assert inventory.rendered_bytes == 23
    assert inventory.total_bytes == 23


def test__artifact_inventory__rejects_duplicate_artifact_ids() -> None:
    with pytest.raises(ValueError, match="must be unique"):
        TranscriptionInputArtifactInventory(
            inventory_id="forged",
            rendered_region_ids=("region", "region"),
            embedded_artifact_ids=(),
            rendered_bytes=0,
            embedded_bytes=0,
            mask_bytes=0,
            total_bytes=0,
        )
