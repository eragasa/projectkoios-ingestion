from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from workflows.reading_transcript_equation_evidence import (
    ReadingTranscriptEquationEvidence,
)

SELECTION_ID = (
    "reference-equation-evidence-selection-inventory:sha256:" + "a" * 64
)
RENDERED_PATH = (
    "books/Fixture/chunks/chunk-001/primary-equations/assembly-001.png"
)


def selected_record() -> dict[str, object]:
    return {
        "assembly_id": "equation-assembly:fixture",
        "candidate_ids": ["equation-candidate:fixture"],
        "disposition": "selected_primary_equation_evidence",
        "assembly_rendered_member": {
            "path": RENDERED_PATH,
            "sha256": "b" * 64,
            "bytes": 128,
        },
        "review_status": "unreviewed",
        "accepted": False,
        "review_required": True,
        "chunk_text_eligible": False,
        "recognized_text_retained": False,
    }


def assembly_evidence() -> dict[str, object]:
    return {
        "assembly_id": "equation-assembly:fixture",
        "candidate_ids": ["equation-candidate:fixture"],
        "sanitized_native_text": "E = mc²",
        "source_labels": ["(1)"],
        "source_spans": [
            {
                "page_index": 3,
                "bounding_box": [10.0, 20.0, 30.0, 40.0],
            }
        ],
    }


def test__equation_evidence__projects_selected_evidence() -> None:
    evidence = ReadingTranscriptEquationEvidence.from_selected_evidence(
        selection_record=selected_record(),
        assembly_evidence=assembly_evidence(),
        selection_inventory_id=SELECTION_ID,
    )

    assert evidence.to_record() == {
        "evidence_type": "equation",
        "assembly_id": "equation-assembly:fixture",
        "candidate_ids": ["equation-candidate:fixture"],
        "selection_disposition": "selected_primary_equation_evidence",
        "selection_inventory_id": SELECTION_ID,
        "recognition_status": "not_requested",
        "native_text_evidence": "E = mc²",
        "source_labels": ["(1)"],
        "source_spans": [
            {
                "page_index": 3,
                "bounding_box": [10.0, 20.0, 30.0, 40.0],
            }
        ],
        "rendered_members": [
            {
                "path": RENDERED_PATH,
                "sha256": "b" * 64,
                "bytes": 128,
            }
        ],
        "recognized_latex": None,
        "recognized_mathml": None,
        "automated": True,
        "review_status": "unreviewed",
        "accepted": False,
        "review_required": True,
        "chunk_text_eligible": False,
    }
    with pytest.raises(FrozenInstanceError):
        evidence.accepted = True  # type: ignore[misc]


def test__equation_evidence__rejects_auxiliary_evidence() -> None:
    selection = selected_record()
    selection["disposition"] = "retained_auxiliary_equation_evidence"

    with pytest.raises(ValueError, match="not selected"):
        ReadingTranscriptEquationEvidence.from_selected_evidence(
            selection_record=selection,
            assembly_evidence=assembly_evidence(),
            selection_inventory_id=SELECTION_ID,
        )


def test__equation_evidence__rejects_mismatched_assembly() -> None:
    assembly = assembly_evidence()
    assembly["assembly_id"] = "equation-assembly:other"

    with pytest.raises(ValueError, match="assembly binding"):
        ReadingTranscriptEquationEvidence.from_selected_evidence(
            selection_record=selected_record(),
            assembly_evidence=assembly,
            selection_inventory_id=SELECTION_ID,
        )


def test__equation_evidence__rejects_changed_review_gate() -> None:
    selection = selected_record()
    selection["chunk_text_eligible"] = True

    with pytest.raises(ValueError, match="review gates"):
        ReadingTranscriptEquationEvidence.from_selected_evidence(
            selection_record=selection,
            assembly_evidence=assembly_evidence(),
            selection_inventory_id=SELECTION_ID,
        )


def test__equation_evidence__rejects_unsafe_rendered_path() -> None:
    selection = selected_record()
    rendered = selection["assembly_rendered_member"]
    assert isinstance(rendered, dict)
    rendered["path"] = "../outside.png"

    with pytest.raises(ValueError, match="rendered path"):
        ReadingTranscriptEquationEvidence.from_selected_evidence(
            selection_record=selection,
            assembly_evidence=assembly_evidence(),
            selection_inventory_id=SELECTION_ID,
        )
