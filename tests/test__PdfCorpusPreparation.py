from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from projectkoios.ingestion.batch_cli import main as ingest_batch
from projectkoios.ingestion.corpus import (
    PdfCorpusError,
    PdfCorpusLimits,
    PdfCorpusPublicationError,
    load_pdf_corpus_plans,
    prepare_pdf_corpus,
    publish_pdf_corpus_plans,
    validate_pdf_corpus,
)
from projectkoios.ingestion.corpus_plan_cli import main as plan_corpus
from projectkoios.ingestion.corpus_validation_cli import (
    main as validate_corpus,
)

FIXTURES = Path(__file__).parent / "fixtures" / "pdf"


def _sources(tmp_path: Path) -> Path:
    source = tmp_path / "sources"
    nested = source / "nested"
    nested.mkdir(parents=True, mode=0o700)
    shutil.copyfile(FIXTURES / "born-digital-text.pdf", source / "first.pdf")
    shutil.copyfile(FIXTURES / "image-only-page.pdf", source / "second.PDF")
    shutil.copyfile(
        FIXTURES / "born-digital-text.pdf", nested / "duplicate.pdf"
    )
    (source / "ignored.txt").write_text("not a PDF\n", encoding="utf-8")
    return source


def test__corpus_planner__discovers_deduplicates_shards_and_publishes_once(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _sources(tmp_path)
    plans = tmp_path / "plans"
    arguments = [
        "--source-root",
        str(source),
        "--output",
        str(plans),
        "--batch-size",
        "1",
    ]

    assert plan_corpus(arguments) == 2
    dry_run = json.loads(capsys.readouterr().out)
    assert dry_run == {
        "discovered_file_count": 3,
        "duplicate_file_count": 1,
        "plan_count": 2,
        "status": "planned",
        "total_source_bytes": sum(
            path.stat().st_size
            for path in (
                source / "first.pdf",
                source / "second.PDF",
                source / "nested/duplicate.pdf",
            )
        ),
        "unique_file_count": 2,
    }
    assert not plans.exists()

    assert plan_corpus([*arguments, "--apply"]) == 0
    created = json.loads(capsys.readouterr().out)
    assert created["action"] == "created"
    assert tuple(path.name for path in sorted(plans.iterdir())) == (
        "batch-00001.json",
        "batch-00002.json",
    )
    assert oct(plans.stat().st_mode & 0o777) == "0o700"
    assert all(
        oct(path.stat().st_mode & 0o777) == "0o600" for path in plans.iterdir()
    )
    loaded = load_pdf_corpus_plans(plans)
    assert tuple(len(plan.items) for plan in loaded) == (1, 1)
    assert loaded[0].items[0].pdf_path.as_posix() == "first.pdf"
    assert all(
        item.output_directory.as_posix() == item.sha256
        for plan in loaded
        for item in plan.items
    )

    assert plan_corpus([*arguments, "--apply"]) == 0
    unchanged = json.loads(capsys.readouterr().out)
    assert unchanged["action"] == "unchanged"


def test__corpus_validation__replays_owner_artifacts_and_reports_limitations(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _sources(tmp_path)
    prepared = prepare_pdf_corpus(source, limits=PdfCorpusLimits(batch_size=1))
    plans = tmp_path / "plans"
    assert publish_pdf_corpus_plans(plans, prepared.plans) == "created"
    output = tmp_path / "output"
    for plan_path in sorted(plans.iterdir()):
        assert (
            ingest_batch(
                [
                    str(plan_path),
                    "--source-root",
                    str(source),
                    "--output-root",
                    str(output),
                    "--apply",
                ]
            )
            == 0
        )
        capsys.readouterr()

    arguments = [
        "--plans",
        str(plans),
        "--source-root",
        str(source),
        "--output-root",
        str(output),
    ]
    assert validate_corpus(arguments) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "valid"
    assert report["document_count"] == 2
    assert report["page_count"] == 2
    assert report["empty_page_count"] == 1
    assert report["documents_requiring_ocr"] == 1
    assert report["low_text_page_count"] == 1
    assert report["limitations"] == [
        "native_text_only",
        "automated_unreviewed",
        "ocr_not_executed",
        "equation_transcription_not_executed",
        "embeddings_not_generated",
        "index_not_generated",
        "not_rag_ready",
    ]
    assert oct(output.stat().st_mode & 0o777) == "0o700"
    for directory in output.iterdir():
        assert oct(directory.stat().st_mode & 0o777) == "0o700"
        assert oct((directory / "pages").stat().st_mode & 0o777) == "0o700"
        assert (
            oct((directory / "extraction.json").stat().st_mode & 0o777)
            == "0o600"
        )
        assert all(
            oct(path.stat().st_mode & 0o777) == "0o600"
            for path in (directory / "pages").iterdir()
        )

    first = prepared.plans[0].items[0]
    artifact = output / first.output_directory / "pages/page-0001.txt"
    artifact.write_text("changed\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="2"):
        validate_corpus(arguments)
    error = capsys.readouterr().err
    assert "page artifact differs from owner evidence" in error
    assert "born-digital" not in error


def test__corpus_planner__rejects_links_bounds_and_plan_collisions(
    tmp_path: Path,
) -> None:
    source = _sources(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (source / "linked").symlink_to(outside, target_is_directory=True)
    with pytest.raises(PdfCorpusError, match="symlinked directory"):
        prepare_pdf_corpus(source)
    (source / "linked").unlink()

    with pytest.raises(PdfCorpusError, match="file count"):
        prepare_pdf_corpus(source, limits=PdfCorpusLimits(max_files=2))
    largest = max(
        (source / "first.pdf").stat().st_size,
        (source / "second.PDF").stat().st_size,
    )
    with pytest.raises(PdfCorpusError, match="aggregate byte"):
        prepare_pdf_corpus(
            source,
            limits=PdfCorpusLimits(
                max_file_bytes=largest,
                max_total_bytes=largest,
            ),
        )

    prepared = prepare_pdf_corpus(source)
    plans = tmp_path / "plans"
    publish_pdf_corpus_plans(plans, prepared.plans)
    plan = next(plans.iterdir())
    plan.write_text("{}\n", encoding="utf-8")
    with pytest.raises(PdfCorpusPublicationError, match="differs"):
        publish_pdf_corpus_plans(plans, prepared.plans)


def test__corpus_validation__rejects_extra_and_nonprivate_artifacts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _sources(tmp_path)
    prepared = prepare_pdf_corpus(source)
    plans = tmp_path / "plans"
    publish_pdf_corpus_plans(plans, prepared.plans)
    output = tmp_path / "output"
    plan_path = next(plans.iterdir())
    assert (
        ingest_batch(
            [
                str(plan_path),
                "--source-root",
                str(source),
                "--output-root",
                str(output),
                "--apply",
            ]
        )
        == 0
    )
    capsys.readouterr()

    summary = validate_pdf_corpus(
        load_pdf_corpus_plans(plans),
        source_root=source,
        output_root=output,
    )
    assert summary.document_count == 2

    first = prepared.plans[0].items[0]
    directory = output / first.output_directory
    (directory / "extra.txt").write_text("extra\n", encoding="utf-8")
    with pytest.raises(PdfCorpusError, match="inventory"):
        validate_pdf_corpus(
            prepared.plans,
            source_root=source,
            output_root=output,
        )
    (directory / "extra.txt").unlink()
    (directory / "extraction.json").chmod(0o644)
    with pytest.raises(PdfCorpusError, match="private permissions"):
        validate_pdf_corpus(
            prepared.plans,
            source_root=source,
            output_root=output,
        )
