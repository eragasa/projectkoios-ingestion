from __future__ import annotations

import hashlib
import json
from dataclasses import FrozenInstanceError, replace

import pytest
from projectkoios.ingestion.json.error import JsonParseError
from projectkoios.ingestion.tables.acceptance.cell import (
    TableEvidenceProposalCell,
)
from projectkoios.ingestion.tables.acceptance.codec import (
    AcceptedTableEvidenceCodec,
    TableEvidenceProposalCodec,
)
from projectkoios.ingestion.tables.acceptance.conflict import (
    TableEvidenceConflictDisposition,
    TableEvidenceConflictKind,
    TableEvidenceConflictResolution,
)
from projectkoios.ingestion.tables.acceptance.decision import (
    ACCEPTANCE_AUTHORITY_SCOPE,
    EXCLUDED_AUTHORITIES,
    TableEvidenceHumanAcceptanceDecision,
)
from projectkoios.ingestion.tables.acceptance.inventory import (
    TableEvidenceConflictInventory,
)
from projectkoios.ingestion.tables.acceptance.observation import (
    TableEvidenceConflictObservation,
)
from projectkoios.ingestion.tables.acceptance.parameter import (
    TableEvidenceParameter,
)
from projectkoios.ingestion.tables.acceptance.proposal import (
    TableEvidenceProposal,
)
from projectkoios.ingestion.tables.acceptance.result import (
    AcceptedTableEvidenceResult,
    AcceptedTableEvidenceStatus,
)
from projectkoios.ingestion.tables.acceptance.row import (
    TableEvidenceProposalRow,
)

PROPOSAL_SHA = "a" * 64
CHECKLIST_SHA = "b" * 64
NOTEBOOK_SHA = "c" * 64


def parameter(index: int) -> TableEvidenceParameter:
    return TableEvidenceParameter(
        parameter_index=index,
        parameter_key=f"parameter_{index}",
        printed_header=f"P({index})",
        unit="eV",
        printed_panel=1 if index == 0 else 2,
    )


def cell(
    row_index: int,
    parameter: TableEvidenceParameter,
    *,
    flag: str | None = None,
) -> TableEvidenceProposalCell:
    value = f"{row_index + parameter.parameter_index + 1}.0000"
    return TableEvidenceProposalCell(
        row_index=row_index,
        parameter_index=parameter.parameter_index,
        parameter_key=parameter.parameter_key,
        printed_header=parameter.printed_header,
        unit=parameter.unit,
        printed_panel=parameter.printed_panel,
        raw_native_text="9.0000" if flag else value,
        proposed_text=value,
        source_bounding_box=(
            10.0 + parameter.parameter_index,
            20.0 + row_index,
            11.0 + parameter.parameter_index,
            21.0 + row_index,
        ),
        independent_ocr_text="8.0000" if flag else value,
        ambiguity_flags=() if flag is None else (flag,),
    )


def proposal() -> TableEvidenceProposal:
    parameters = (parameter(0), parameter(1))
    rows = tuple(
        TableEvidenceProposalRow(
            row_index=row_index,
            compound=f"Compound{row_index}",
            cells=tuple(
                cell(
                    row_index,
                    item,
                    flag=(
                        "native-render-disagreement"
                        if (row_index, item.parameter_index) == (0, 0)
                        else "independent-ocr-disagreement"
                        if (row_index, item.parameter_index) == (1, 1)
                        else None
                    ),
                )
                for item in parameters
            ),
        )
        for row_index in range(2)
    )
    return TableEvidenceProposal(
        proposal_sha256=PROPOSAL_SHA,
        source_id="doi:fixture",
        source_blob_id="blob:sha256:" + "d" * 64,
        source_sha256="d" * 64,
        source_byte_length=100,
        source_media_type="application/pdf",
        rights_access_status="rights-unresolved",
        physical_page_index=3,
        physical_page_number=4,
        printed_page_label="368",
        reading_page_location_id=("reading-page-location:sha256:" + "e" * 64),
        rendered_region_id="rendered-region:sha256:" + "f" * 64,
        rendered_region_sha256="1" * 64,
        source_bounding_box=(0.0, 0.0, 100.0, 100.0),
        coordinate_system="fixture-points",
        resolution_dpi=600,
        parameters=parameters,
        rows=rows,
    )


def observation(
    proposal_value: TableEvidenceProposal,
    kind: TableEvidenceConflictKind,
    row: int,
    column: int,
) -> TableEvidenceConflictObservation:
    target = proposal_value.rows[row].cells[column]
    observed_text = (
        target.raw_native_text
        if kind is TableEvidenceConflictKind.NATIVE_EXTRACTION
        else target.independent_ocr_text
        if kind is TableEvidenceConflictKind.INDEPENDENT_OCR
        else "9.0000"
    )
    return TableEvidenceConflictObservation(
        kind=kind,
        observation_sha256=(
            NOTEBOOK_SHA
            if kind is TableEvidenceConflictKind.EXTERNAL_NOTEBOOK
            else CHECKLIST_SHA
        ),
        cell_id=target.cell_id,
        observed_text=observed_text,
        proposed_text=target.proposed_text,
    )


def inventory(
    proposal_value: TableEvidenceProposal,
) -> TableEvidenceConflictInventory:
    return TableEvidenceConflictInventory(
        machine_checklist_sha256=CHECKLIST_SHA,
        external_notebook_cross_check_sha256=NOTEBOOK_SHA,
        native_extraction_conflict_count=1,
        independent_ocr_conflict_count=1,
        external_notebook_conflict_count=1,
        observations=(
            observation(
                proposal_value,
                TableEvidenceConflictKind.NATIVE_EXTRACTION,
                0,
                0,
            ),
            observation(
                proposal_value,
                TableEvidenceConflictKind.INDEPENDENT_OCR,
                1,
                1,
            ),
            observation(
                proposal_value,
                TableEvidenceConflictKind.EXTERNAL_NOTEBOOK,
                0,
                1,
            ),
        ),
    )


def disposition(
    observation_value: TableEvidenceConflictObservation,
) -> TableEvidenceConflictDisposition:
    return TableEvidenceConflictDisposition(
        kind=observation_value.kind,
        observation_sha256=observation_value.observation_sha256,
        cell_id=observation_value.cell_id,
        observed_text=observation_value.observed_text,
        accepted_text=observation_value.proposed_text,
        resolution=(
            TableEvidenceConflictResolution.ACCEPT_EXACT_PROPOSAL_VALUE
        ),
    )


def decision(
    proposal_value: TableEvidenceProposal,
    inventory_value: TableEvidenceConflictInventory,
) -> TableEvidenceHumanAcceptanceDecision:
    return TableEvidenceHumanAcceptanceDecision(
        proposal_id=proposal_value.proposal_id,
        proposal_sha256=proposal_value.proposal_sha256,
        conflict_inventory_id=inventory_value.inventory_id,
        machine_checklist_sha256=CHECKLIST_SHA,
        external_notebook_cross_check_sha256=NOTEBOOK_SHA,
        actor_id="local-operator:fixture",
        verification_basis="explicit interactive operator instruction",
        instruction_message_id="fixture-message",
        instruction_observed_at_utc="2026-10-22T15:55:05.674Z",
        recorded_at_utc="2026-10-22T16:00:00.000Z",
        acceptance_basis="explicit acceptance of the exact proposal",
        authority_scope=ACCEPTANCE_AUTHORITY_SCOPE,
        excluded_authorities=EXCLUDED_AUTHORITIES,
        conflict_dispositions=tuple(
            disposition(item) for item in inventory_value.observations
        ),
    )


def result() -> AcceptedTableEvidenceResult:
    proposed = proposal()
    inventory_value = inventory(proposed)
    return AcceptedTableEvidenceResult.create(
        proposal=proposed,
        conflict_inventory=inventory_value,
        decision=decision(proposed, inventory_value),
    )


def test__accepted_table_evidence__binds_complete_proposal_and_decision() -> (
    None
):
    value = result()

    assert value.status is AcceptedTableEvidenceStatus.ACCEPTED
    assert (value.compound_count, value.parameter_count) == (2, 2)
    assert value.numeric_cell_count == 4
    assert value.decision.actor_id == "local-operator:fixture"
    assert value.decision.excluded_authorities == EXCLUDED_AUTHORITIES
    assert value.result_id.startswith("accepted-table-evidence-result:sha256:")


def test__accepted_table_evidence__strict_codec_replays_exact_bytes() -> None:
    codec = AcceptedTableEvidenceCodec()
    original = result()
    payload = codec.encode(original)

    loaded = codec.decode_result(payload=payload)
    inventory_loaded = codec.decode_inventory(
        payload=codec.encode(original.conflict_inventory)
    )
    decision_loaded = codec.decode_decision(
        payload=codec.encode(original.decision)
    )

    assert loaded == original
    assert codec.encode(loaded) == payload
    assert inventory_loaded == original.conflict_inventory
    assert decision_loaded == original.decision


@pytest.mark.parametrize("removed_index", [0, 2])
def test__accepted_table_evidence__rejects_missing_disposition(
    removed_index: int,
) -> None:
    proposed = proposal()
    inventory_value = inventory(proposed)
    original = decision(proposed, inventory_value)
    incomplete = replace(
        original,
        conflict_dispositions=tuple(
            item
            for index, item in enumerate(original.conflict_dispositions)
            if index != removed_index
        ),
    )

    with pytest.raises(ValueError, match="every inventoried conflict"):
        AcceptedTableEvidenceResult.create(
            proposal=proposed,
            conflict_inventory=inventory_value,
            decision=incomplete,
        )


def test__accepted_table_evidence__rejects_changed_disposition() -> None:
    proposed = proposal()
    inventory_value = inventory(proposed)
    original = decision(proposed, inventory_value)
    changed = replace(original.conflict_dispositions[0], observed_text="7.0000")
    changed_decision = replace(
        original,
        conflict_dispositions=(changed,) + original.conflict_dispositions[1:],
    )

    with pytest.raises(ValueError, match="exact observation"):
        AcceptedTableEvidenceResult.create(
            proposal=proposed,
            conflict_inventory=inventory_value,
            decision=changed_decision,
        )


def test__accepted_table_evidence__rejects_changed_accepted_value() -> None:
    proposed = proposal()
    inventory_value = inventory(proposed)
    original = decision(proposed, inventory_value)
    changed = replace(original.conflict_dispositions[0], accepted_text="7.0000")
    changed_decision = replace(
        original,
        conflict_dispositions=(changed,) + original.conflict_dispositions[1:],
    )

    with pytest.raises(ValueError, match="exact observation"):
        AcceptedTableEvidenceResult.create(
            proposal=proposed,
            conflict_inventory=inventory_value,
            decision=changed_decision,
        )


def test__accepted_table_evidence__rejects_changed_machine_observation() -> (
    None
):
    proposed = proposal()
    original = inventory(proposed)
    changed_observation = replace(
        original.observations[0], observed_text="7.0000"
    )
    changed_inventory = replace(
        original,
        observations=(changed_observation,) + original.observations[1:],
    )
    changed_decision = decision(proposed, changed_inventory)

    with pytest.raises(ValueError, match="preserved proposal evidence"):
        AcceptedTableEvidenceResult.create(
            proposal=proposed,
            conflict_inventory=changed_inventory,
            decision=changed_decision,
        )


def test__acceptance_decision__rejects_recording_before_instruction() -> None:
    proposed = proposal()
    inventory_value = inventory(proposed)
    original = decision(proposed, inventory_value)

    with pytest.raises(ValueError, match="cannot precede"):
        replace(original, recorded_at_utc="2020-01-01T00:00:00Z")


def test__accepted_table_evidence__rejects_bad_json_shape() -> None:
    codec = AcceptedTableEvidenceCodec()
    payload = codec.encode(result())
    value = json.loads(payload)
    value["unknown"] = True
    changed = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()

    with pytest.raises(JsonParseError, match="fields differ"):
        codec.decode_result(payload=changed)

    with pytest.raises(JsonParseError, match="noncanonical"):
        codec.decode_result(payload=b" " + payload)


def test__accepted_table_evidence__is_immutable_and_identity_checked() -> None:
    value = result()

    with pytest.raises(FrozenInstanceError):
        value.compound_count = 3  # type: ignore[misc]
    with pytest.raises(ValueError, match="closure counts"):
        replace(value, numeric_cell_count=3)
    with pytest.raises(JsonParseError, match="identity field"):
        payload = AcceptedTableEvidenceCodec.encode(value).replace(
            value.result_id.encode(),
            ("accepted-table-evidence-result:sha256:" + "0" * 64).encode(),
        )
        AcceptedTableEvidenceCodec().decode_result(payload=payload)


def test__table_proposal_codec__requires_exact_sha_and_complete_schema() -> (
    None
):
    value = {
        "artifact_kind": "private-unaccepted-table-transcription-proposal",
        "schema_version": 1,
        "authority_status": "not-owner-typed-table-evidence",
        "acceptance_status": "unaccepted-human-proofreading-required",
        "source": {
            "source_id": "doi:fixture",
            "source_blob_id": "blob:sha256:" + "d" * 64,
            "source_sha256": "d" * 64,
            "source_byte_length": 100,
            "media_type": "application/pdf",
            "locator": "https://example.invalid/fixture.pdf",
            "rights_access_status": "rights-unresolved",
        },
        "page": {
            "physical_page_index": 3,
            "physical_page_number": 4,
            "printed_page_label": "368",
            "reading_page_location_id": (
                "reading-page-location:sha256:" + "e" * 64
            ),
            "printed_label_basis": "visible",
        },
        "region": {
            "rendered_region_id": "rendered-region:sha256:" + "f" * 64,
            "source_bounding_box": [0.0, 0.0, 100.0, 100.0],
            "effective_source_bounding_box": [0.0, 0.0, 100.0, 100.0],
            "coordinate_system": "fixture-points",
            "resolution_dpi": 600,
            "content_sha256": "1" * 64,
            "byte_length": 10,
            "width_pixels": 10,
            "height_pixels": 10,
        },
        "title_observation": {},
        "parameters": [
            {
                "parameter_index": 0,
                "parameter_key": "parameter_0",
                "printed_header": "P(0)",
                "unit": "eV",
                "printed_panel": 1,
            }
        ],
        "rows": [
            {
                "row_index": 0,
                "compound": "Fixture",
                "compound_observations": [],
                "cells": [
                    {
                        "parameter_index": 0,
                        "parameter_key": "parameter_0",
                        "printed_header": "P(0)",
                        "unit": "eV",
                        "panel": 1,
                        "raw_native_text": "1.0000",
                        "normalized_proposed_text": "1.0000",
                        "source_bounding_box": [1.0, 1.0, 2.0, 2.0],
                        "native_word_locators": [],
                        "independent_ocr_text": "1.0000",
                        "ambiguity_flags": [],
                    }
                ],
            }
        ],
        "closure": {
            "compound_rows": 1,
            "parameter_columns": 1,
            "numeric_parameter_cells": 1,
            "typed_authority_closure": False,
            "human_proofreading_closure": False,
        },
        "limitations": [],
    }
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(payload).hexdigest()

    loaded = TableEvidenceProposalCodec().decode(
        payload=payload, expected_sha256=digest
    )

    assert loaded.cell_count == 1
    with pytest.raises(JsonParseError, match="SHA-256 differs"):
        TableEvidenceProposalCodec().decode(
            payload=payload, expected_sha256="0" * 64
        )
