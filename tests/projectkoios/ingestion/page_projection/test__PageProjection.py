from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from projectkoios.ingestion.page_projection import (
    OwnerValidatedPageProjection,
    PageProjectionPlanEntry,
    PageProjectionValidationError,
    iter_page_projection_pages,
    iter_page_projection_windows,
    load_owner_validated_page_projection,
    load_page_projection_validation_report,
    page_projection_validation_report_bytes,
    validate_page_projection,
)

_PNG = b"\x89PNG\r\n\x1a\nowner-test"


def _private_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_bytes(content)
    path.chmod(0o600)


def _fixture(
    tmp_path: Path,
    *,
    first_paragraph: str = "As shown in Figure 0.3, the response is nonlinear.",
    equation_native_text: str = "x = y",
    second_media_path: str = "media/equation.png",
) -> tuple[PageProjectionPlanEntry, dict[str, Path]]:
    source = b"private source PDF bytes"
    plan = PageProjectionPlanEntry(
        document_id="doc-06",
        filename="NeamanSemiconductorPhysicsAndDevices.pdf",
        title="Semiconductor Physics and Devices",
        source_sha256=hashlib.sha256(source).hexdigest(),
        expected_page_count=2,
    )
    pages = [
        {
            "physical_page": 1,
            "printed_page": "xix",
            "citation": {"physical_page": 1, "printed_page": "xix"},
            "blocks": [
                {"type": "paragraph", "text": first_paragraph, "order": 0},
                {
                    "type": "figure",
                    "png_path": "media/figure.png",
                    "caption": "Figure 0.3",
                    "associations": [],
                    "status": "associated_unreviewed",
                    "order": 1,
                },
            ],
        },
        {
            "physical_page": 2,
            "printed_page": "1",
            "citation": {"physical_page": 2, "printed_page": "1"},
            "blocks": [
                {
                    "type": "paragraph",
                    "text": "Charge transport remains the chapter topic.",
                    "style": "heading",
                    "order": 0,
                },
                {
                    "type": "equation",
                    "native_text": equation_native_text,
                    "latex": None,
                    "mathml": None,
                    "png_path": second_media_path,
                    "status": "not_requested_pending_evidence",
                    "recognition_status": "not_requested",
                    "accepted": False,
                    "review_required": True,
                    "chunk_text_eligible": False,
                    "order": 1,
                },
            ],
        },
    ]
    transcript = (
        "\n".join(
            json.dumps(page, ensure_ascii=False, separators=(",", ":"))
            for page in pages
        )
        + "\n"
    ).encode()
    summary = {
        "status": "complete",
        "pages": 2,
        "paragraphs": 2,
        "headings": 1,
        "figures": 1,
        "primary_equations": 1,
        "utf8_bytes": len(transcript),
    }
    baseline = {
        "complete": True,
        "page_count": 2,
        "pages": [
            {"printed_page_label": "xix", "text": first_paragraph * 2},
            {
                "printed_page_label": "1",
                "text": "Charge transport remains the chapter topic." * 2,
            },
        ],
    }
    paths = {
        "source": tmp_path / "document.pdf",
        "transcript": tmp_path / "reading-transcript.jsonl",
        "summary": tmp_path / "reading-transcript-summary.json",
        "baseline": tmp_path / "composed-transcript.json",
        "media_root": tmp_path,
        "report": tmp_path / "reading-transcript-validation.json",
    }
    _private_write(paths["source"], source)
    _private_write(paths["transcript"], transcript)
    _private_write(paths["summary"], json.dumps(summary).encode())
    _private_write(paths["baseline"], json.dumps(baseline).encode())
    _private_write(tmp_path / "media" / "figure.png", _PNG)
    _private_write(tmp_path / "media" / "equation.png", _PNG + b"2")
    return plan, paths


def _validate(
    plan: PageProjectionPlanEntry, paths: dict[str, Path]
) -> OwnerValidatedPageProjection:
    return validate_page_projection(
        plan,
        source_path=paths["source"],
        transcript_path=paths["transcript"],
        summary_path=paths["summary"],
        baseline_path=paths["baseline"],
        media_root=paths["media_root"],
    )


def test__page_projection__validates_and_loads_text_only_pages(
    tmp_path: Path,
) -> None:
    plan, paths = _fixture(tmp_path)

    projection = _validate(plan, paths)
    _private_write(
        paths["report"],
        page_projection_validation_report_bytes(projection.report),
    )
    loaded_report = load_page_projection_validation_report(paths["report"])
    loaded = load_owner_validated_page_projection(
        plan,
        transcript_path=paths["transcript"],
        validation_report_path=paths["report"],
    )

    assert loaded_report == projection.report
    assert loaded == projection
    assert [
        page.physical_page for page in iter_page_projection_pages(loaded)
    ] == [
        1,
        2,
    ]
    assert tuple(
        (block.text, block.style)
        for page in loaded.pages
        for block in page.text_blocks
    ) == (
        ("As shown in Figure 0.3, the response is nonlinear.", None),
        ("Figure 0.3", "caption"),
        ("Charge transport remains the chapter topic.", "heading"),
    )
    assert (
        sum(
            block.style == "caption"
            for page in loaded.pages
            for block in page.text_blocks
        )
        == 1
    )
    assert not hasattr(loaded.pages[0], "media")
    assert not hasattr(loaded.pages[1], "equations")


def test__page_projection__caption_reference_is_not_caption_duplication(
    tmp_path: Path,
) -> None:
    plan, paths = _fixture(tmp_path)

    projection = _validate(plan, paths)

    assert projection.report.figure_count == 1


def test__page_projection__rejects_exact_caption_paragraph(
    tmp_path: Path,
) -> None:
    plan, paths = _fixture(tmp_path, first_paragraph="Figure 0.3")

    with pytest.raises(
        PageProjectionValidationError,
        match="caption is projected as a paragraph",
    ):
        _validate(plan, paths)


def test__page_projection__rejects_equation_text_in_paragraph(
    tmp_path: Path,
) -> None:
    plan, paths = _fixture(
        tmp_path,
        equation_native_text="Charge transport remains the chapter topic.",
    )

    with pytest.raises(
        PageProjectionValidationError,
        match="equation evidence is projected as a paragraph",
    ):
        _validate(plan, paths)


def test__page_projection__rejects_reused_or_unsafe_media_path(
    tmp_path: Path,
) -> None:
    plan, paths = _fixture(
        tmp_path,
        second_media_path="media/figure.png",
    )
    with pytest.raises(PageProjectionValidationError, match="referenced twice"):
        _validate(plan, paths)

    plan, paths = _fixture(
        tmp_path / "unsafe",
        second_media_path="../equation.png",
    )
    with pytest.raises(
        PageProjectionValidationError, match="media path is unsafe"
    ):
        _validate(plan, paths)


def test__page_projection__replay_and_window_boundaries_do_not_change_identity(
    tmp_path: Path,
) -> None:
    plan, paths = _fixture(tmp_path)

    first = _validate(plan, paths)
    second = _validate(plan, paths)
    one_page_windows = tuple(
        iter_page_projection_windows(first, maximum_pages=1)
    )
    two_page_windows = tuple(
        iter_page_projection_windows(first, maximum_pages=2)
    )

    assert first == second
    assert page_projection_validation_report_bytes(first.report) == (
        page_projection_validation_report_bytes(second.report)
    )
    assert (
        tuple(page for window in one_page_windows for page in window)
        == first.pages
    )
    assert (
        tuple(page for window in two_page_windows for page in window)
        == first.pages
    )
    assert (
        first.report.page_projection_sha256
        == second.report.page_projection_sha256
    )


def test__page_projection__external_plan_cannot_self_assert_validation(
    tmp_path: Path,
) -> None:
    plan, paths = _fixture(tmp_path)
    projection = _validate(plan, paths)
    _private_write(
        paths["report"],
        page_projection_validation_report_bytes(projection.report),
    )
    unvalidated_plan = replace(plan, document_id="doc-attacker")

    with pytest.raises(ValueError, match="plan and validation report differ"):
        load_owner_validated_page_projection(
            unvalidated_plan,
            transcript_path=paths["transcript"],
            validation_report_path=paths["report"],
        )

    payload = json.loads(paths["report"].read_text())
    payload["paragraph_count"] = 999
    _private_write(paths["report"], json.dumps(payload).encode())
    with pytest.raises(PageProjectionValidationError, match="malformed"):
        load_page_projection_validation_report(paths["report"])
