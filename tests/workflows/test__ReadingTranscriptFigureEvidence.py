from __future__ import annotations

import pytest

from workflows.reading_transcript_figure_evidence import (
    ReadingTranscriptFigureEvidence,
)

CANDIDATE_ID = "figure-candidate:sha256:" + "a" * 64
RENDERED_PATH = "books/Fixture/chunks/chunk-001/figures/figure-001.png"


def figure_evidence() -> dict[str, object]:
    return {
        "candidate_id": CANDIDATE_ID,
        "evidence_status": "proposed",
        "confidence": 0.9,
        "source_label": "Figure 1",
        "source_spans": [
            {"page_index": 4, "bounding_box": [1.0, 2.0, 3.0, 4.0]}
        ],
        "associations": [
            {
                "association_id": "figure-text-association:fixture",
                "role": "caption",
                "text": "Figure 1 caption.",
            }
        ],
        "rendered_members": ["figures/figure-001.png"],
    }


def rendered_members() -> list[dict[str, object]]:
    return [
        {
            "path": RENDERED_PATH,
            "sha256": "b" * 64,
            "bytes": 128,
        }
    ]


def test__figure_evidence__projects_unreviewed_record() -> None:
    evidence = ReadingTranscriptFigureEvidence.from_quality_evidence(
        figure_evidence=figure_evidence(),
        rendered_members=rendered_members(),
    )

    assert evidence.candidate_id == CANDIDATE_ID
    assert evidence.page_index == 4
    assert evidence.rendered_paths == (RENDERED_PATH,)
    assert evidence.to_record() == {
        "evidence_type": "figure",
        "candidate_id": CANDIDATE_ID,
        "evidence_status": "proposed",
        "confidence": 0.9,
        "source_label": "Figure 1",
        "source_spans": [
            {"page_index": 4, "bounding_box": [1.0, 2.0, 3.0, 4.0]}
        ],
        "associations": [
            {
                "association_id": "figure-text-association:fixture",
                "role": "caption",
                "text": "Figure 1 caption.",
            }
        ],
        "rendered_members": [
            {
                "path": RENDERED_PATH,
                "sha256": "b" * 64,
                "bytes": 128,
            }
        ],
        "automated": True,
        "accepted": False,
        "review_required": True,
    }


def test__figure_evidence__returns_detached_records() -> None:
    evidence = ReadingTranscriptFigureEvidence.from_quality_evidence(
        figure_evidence=figure_evidence(),
        rendered_members=rendered_members(),
    )
    record = evidence.to_record()
    record["accepted"] = True

    assert evidence.to_record()["accepted"] is False


def test__figure_evidence__rejects_cross_page_spans() -> None:
    figure = figure_evidence()
    spans = figure["source_spans"]
    assert isinstance(spans, list)
    spans.append({"page_index": 5, "bounding_box": None})

    with pytest.raises(ValueError, match="one page"):
        ReadingTranscriptFigureEvidence.from_quality_evidence(
            figure_evidence=figure,
            rendered_members=rendered_members(),
        )


def test__figure_evidence__rejects_rendered_path_mismatch() -> None:
    members = rendered_members()
    members[0]["path"] = "books/Fixture/chunks/chunk-001/figures/other.png"

    with pytest.raises(ValueError, match="path binding"):
        ReadingTranscriptFigureEvidence.from_quality_evidence(
            figure_evidence=figure_evidence(),
            rendered_members=members,
        )


def test__figure_evidence__retains_unlocated_geometry() -> None:
    figure = figure_evidence()
    figure["source_spans"] = [{"page_index": 4, "bounding_box": None}]

    evidence = ReadingTranscriptFigureEvidence.from_quality_evidence(
        figure_evidence=figure,
        rendered_members=rendered_members(),
    )

    assert evidence.to_record()["source_spans"] == [
        {"page_index": 4, "bounding_box": None}
    ]
