from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from workflows.equation_evidence_selection import EquationEvidenceSelection


def test__equation_evidence_selection__selects_display_proposals() -> None:
    selection = EquationEvidenceSelection.from_assembly_evidence(
        kind="display",
        rejected=False,
        detector_evidence_statuses=("proposed", "proposed"),
    )

    assert selection.disposition == "selected_primary_equation_evidence"
    assert selection.ineligibility_reasons == ()
    assert selection.review_status == "unreviewed"
    assert selection.accepted is False
    assert selection.review_required is True
    assert selection.chunk_text_eligible is False
    assert selection.recognized_text_retained is False
    with pytest.raises(FrozenInstanceError):
        selection.accepted = True  # type: ignore[misc]


def test__equation_evidence_selection__retains_non_primary_evidence() -> None:
    inline = EquationEvidenceSelection.from_assembly_evidence(
        kind="inline",
        rejected=False,
        detector_evidence_statuses=("proposed",),
    )
    ambiguous = EquationEvidenceSelection.from_assembly_evidence(
        kind="display",
        rejected=False,
        detector_evidence_statuses=("ambiguous",),
    )

    assert inline.disposition == "retained_auxiliary_equation_evidence"
    assert inline.ineligibility_reasons == ("assembly_kind_not_display",)
    assert ambiguous.disposition == "retained_auxiliary_equation_evidence"
    assert ambiguous.ineligibility_reasons == (
        "detector_evidence_not_proposed",
    )


def test__equation_evidence_selection__retains_rejected_evidence() -> None:
    selection = EquationEvidenceSelection.from_assembly_evidence(
        kind="inline",
        rejected=True,
        detector_evidence_statuses=("ambiguous",),
    )

    assert selection.disposition == "retained_rejected_equation_evidence"
    assert selection.ineligibility_reasons == (
        "assembly_kind_not_display",
        "assembly_rejected",
        "detector_evidence_not_proposed",
    )


def test__equation_evidence_selection__rejects_invalid_source_evidence() -> (
    None
):
    with pytest.raises(ValueError, match="kind"):
        EquationEvidenceSelection.from_assembly_evidence(
            kind="unknown",
            rejected=False,
            detector_evidence_statuses=("proposed",),
        )
    with pytest.raises(TypeError, match="boolean"):
        EquationEvidenceSelection.from_assembly_evidence(
            kind="display",
            rejected=0,  # type: ignore[arg-type]
            detector_evidence_statuses=("proposed",),
        )
    with pytest.raises(ValueError, match="statuses"):
        EquationEvidenceSelection.from_assembly_evidence(
            kind="display",
            rejected=False,
            detector_evidence_statuses=(),
        )
