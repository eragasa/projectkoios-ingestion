from __future__ import annotations

import pytest

from workflows.reading_transcript_table_evidence import (
    ReadingTranscriptTableEvidence,
)

CANDIDATE_ID = "table-candidate:sha256:" + "a" * 64
REGION_ONE = "table-region-evidence:sha256:" + "b" * 64
REGION_TWO = "table-region-evidence:sha256:" + "c" * 64
PATH_ONE = "books/Fixture/chunks/chunk-001/tables/table-001-region-01.png"
PATH_TWO = "books/Fixture/chunks/chunk-001/tables/table-001-region-02.png"


def table_evidence() -> dict[str, object]:
    return {
        "candidate_id": CANDIDATE_ID,
        "evidence_status": "proposed",
        "confidence": 0.8,
        "boundary_kind": "ruled",
        "source_label": "Table 1",
        "source_spans": [
            {"page_index": 4, "bounding_box": [1.0, 2.0, 3.0, 4.0]},
            {"page_index": 5, "bounding_box": None},
        ],
        "associations": [],
        "rendered_members": [
            "tables/table-001-region-01.png",
            "tables/table-001-region-02.png",
        ],
        "region_evidence_ids": [REGION_ONE, REGION_TWO],
    }


def rendered_members() -> list[dict[str, object]]:
    return [
        {
            "path": PATH_ONE,
            "sha256": "d" * 64,
            "bytes": 128,
            "candidate_id": CANDIDATE_ID,
            "page_index": 4,
            "region_evidence_id": REGION_ONE,
        },
        {
            "path": PATH_TWO,
            "sha256": "e" * 64,
            "bytes": 256,
            "candidate_id": CANDIDATE_ID,
            "page_index": 5,
            "region_evidence_id": REGION_TWO,
        },
    ]


def test__table_evidence__projects_one_record_per_page() -> None:
    records = ReadingTranscriptTableEvidence.from_quality_evidence(
        table_evidence=table_evidence(),
        rendered_members=rendered_members(),
    )

    assert [record.page_index for record in records] == [4, 5]
    assert all(record.candidate_id == CANDIDATE_ID for record in records)
    assert records[0].rendered_paths == (PATH_ONE,)
    assert records[1].region_evidence_ids == (REGION_TWO,)
    assert records[0].to_record() == {
        "evidence_type": "table",
        "candidate_id": CANDIDATE_ID,
        "evidence_status": "proposed",
        "confidence": 0.8,
        "boundary_kind": "ruled",
        "source_label": "Table 1",
        "source_spans": [
            {"page_index": 4, "bounding_box": [1.0, 2.0, 3.0, 4.0]}
        ],
        "associations": [],
        "rendered_members": [
            {
                "path": PATH_ONE,
                "sha256": "d" * 64,
                "bytes": 128,
                "region_evidence_id": REGION_ONE,
            }
        ],
        "automated": True,
        "accepted": False,
        "review_required": True,
    }
    assert records[1].to_record()["source_spans"] == [
        {"page_index": 5, "bounding_box": None}
    ]


def test__table_evidence__returns_detached_records() -> None:
    record = ReadingTranscriptTableEvidence.from_quality_evidence(
        table_evidence=table_evidence(),
        rendered_members=rendered_members(),
    )[0]
    value = record.to_record()
    value["accepted"] = True

    assert record.to_record()["accepted"] is False


def test__table_evidence__rejects_region_identity_mismatch() -> None:
    members = rendered_members()
    members[0]["region_evidence_id"] = REGION_TWO

    with pytest.raises(ValueError, match="rendered-region binding"):
        ReadingTranscriptTableEvidence.from_quality_evidence(
            table_evidence=table_evidence(),
            rendered_members=members,
        )


def test__table_evidence__rejects_candidate_identity_mismatch() -> None:
    members = rendered_members()
    members[0]["candidate_id"] = "table-candidate:sha256:" + "f" * 64

    with pytest.raises(ValueError, match="rendered-region binding"):
        ReadingTranscriptTableEvidence.from_quality_evidence(
            table_evidence=table_evidence(),
            rendered_members=members,
        )


def test__table_evidence__rejects_page_coverage_mismatch() -> None:
    members = rendered_members()
    members[1]["page_index"] = 4

    with pytest.raises(ValueError, match="page coverage"):
        ReadingTranscriptTableEvidence.from_quality_evidence(
            table_evidence=table_evidence(),
            rendered_members=members,
        )


def test__table_evidence__rejects_unsafe_rendered_path() -> None:
    members = rendered_members()
    members[0]["path"] = "../table.png"

    with pytest.raises(ValueError, match="rendered path"):
        ReadingTranscriptTableEvidence.from_quality_evidence(
            table_evidence=table_evidence(),
            rendered_members=members,
        )
