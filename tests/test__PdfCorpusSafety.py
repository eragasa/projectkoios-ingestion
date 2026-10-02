from __future__ import annotations

import os
from pathlib import Path, PurePosixPath

import pytest
from projectkoios.ingestion import PdfBatchItem, PdfBatchPlan
from projectkoios.ingestion import corpus as corpus_module
from projectkoios.ingestion.corpus import (
    PdfCorpusError,
    PdfCorpusLimits,
    PdfCorpusPublicationError,
    load_pdf_corpus_plans,
    prepare_pdf_corpus,
    publish_pdf_corpus_plans,
    validate_pdf_corpus,
)


def _item(index: int, *, byte_size: int = 1) -> PdfBatchItem:
    digest = f"{index:064x}"
    return PdfBatchItem(
        source_id=f"pdf:sha256:{digest}",
        pdf_path=PurePosixPath(f"source-{index:05d}.pdf"),
        output_directory=PurePosixPath(digest),
        sha256=digest,
        byte_size=byte_size,
        locator=f"source-{index:05d}.pdf",
    )


def _plans(*items: PdfBatchItem) -> tuple[PdfBatchPlan, ...]:
    return tuple(
        PdfBatchPlan(schema_version=1, items=items[offset : offset + 256])
        for offset in range(0, len(items), 256)
    )


def test__corpus_plan_publication__does_not_replace_destination_that_appears(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "plans"
    plans = _plans(_item(1))
    original = corpus_module._rename_directory_no_replace

    def destination_appears(source: Path, destination: Path) -> None:
        destination.mkdir(mode=0o700)
        original(source, destination)

    monkeypatch.setattr(
        corpus_module,
        "_rename_directory_no_replace",
        destination_appears,
    )

    with pytest.raises(PdfCorpusPublicationError, match="appeared"):
        publish_pdf_corpus_plans(target, plans)

    assert target.is_dir()
    assert not tuple(target.iterdir())
    assert not tuple(tmp_path.glob(".plans.tmp-*"))


def test__corpus_limits__accept_hard_boundaries_and_reject_overages() -> None:
    assert (
        PdfCorpusLimits(
            max_files=10_000,
            max_file_bytes=512_000_000,
            max_total_bytes=10_000_000_000,
        ).max_files
        == 10_000
    )

    with pytest.raises(PdfCorpusError, match="max_files"):
        PdfCorpusLimits(max_files=10_001)
    with pytest.raises(PdfCorpusError, match="max_file_bytes"):
        PdfCorpusLimits(
            max_file_bytes=512_000_001,
            max_total_bytes=10_000_000_000,
        )
    with pytest.raises(PdfCorpusError, match="max_total_bytes"):
        PdfCorpusLimits(max_total_bytes=10_000_000_001)


def test__corpus_plan_bounds__apply_across_multiple_valid_plans(
    tmp_path: Path,
) -> None:
    boundary = (_item(1, byte_size=2), _item(2, byte_size=3))
    plans = (PdfBatchPlan(1, (boundary[0],)), PdfBatchPlan(1, (boundary[1],)))
    limits = PdfCorpusLimits(
        max_files=2,
        max_file_bytes=3,
        max_total_bytes=5,
    )
    target = tmp_path / "plans"

    assert publish_pdf_corpus_plans(target, plans, limits=limits) == "created"
    assert load_pdf_corpus_plans(target, limits=limits) == plans

    item_limited = PdfCorpusLimits(
        max_files=1,
        max_file_bytes=3,
        max_total_bytes=5,
    )
    unpublished = tmp_path / "unpublished/plans"
    with pytest.raises(PdfCorpusError, match="item count"):
        publish_pdf_corpus_plans(
            unpublished,
            plans,
            limits=item_limited,
        )
    assert not unpublished.parent.exists()
    with pytest.raises(PdfCorpusError, match="item count"):
        load_pdf_corpus_plans(target, limits=item_limited)
    with pytest.raises(PdfCorpusError, match="item count"):
        validate_pdf_corpus(
            plans,
            source_root=tmp_path / "absent-source",
            output_root=tmp_path / "absent-output",
            limits=item_limited,
        )

    aggregate_limited = PdfCorpusLimits(
        max_files=2,
        max_file_bytes=3,
        max_total_bytes=4,
    )
    aggregate_target = tmp_path / "aggregate/plans"
    with pytest.raises(PdfCorpusError, match="aggregate byte"):
        publish_pdf_corpus_plans(
            aggregate_target,
            plans,
            limits=aggregate_limited,
        )
    assert not aggregate_target.parent.exists()
    with pytest.raises(PdfCorpusError, match="aggregate byte"):
        load_pdf_corpus_plans(target, limits=aggregate_limited)
    with pytest.raises(PdfCorpusError, match="aggregate byte"):
        validate_pdf_corpus(
            plans,
            source_root=tmp_path / "absent-source",
            output_root=tmp_path / "absent-output",
            limits=aggregate_limited,
        )


def test__corpus_discovery__fails_closed_when_nested_scan_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source"
    nested = source / "nested"
    nested.mkdir(parents=True)
    original = os.scandir

    def fail_nested(path: os.PathLike[str] | str) -> os.ScandirIterator[str]:
        if Path(path) == nested:
            raise PermissionError("injected nested scan failure")
        return original(path)

    monkeypatch.setattr(os, "scandir", fail_nested)

    with pytest.raises(PdfCorpusError, match="source discovery failed"):
        prepare_pdf_corpus(source)


@pytest.mark.parametrize(
    ("maximum_entries", "expected_next_calls"),
    ((0, 1), (2, 3)),
)
def test__bounded_directory_inventory__stops_after_one_excess_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    maximum_entries: int,
    expected_next_calls: int,
) -> None:
    class ControlledEntries:
        def __init__(self) -> None:
            self.next_calls = 0
            self.closed = False

        def __enter__(self) -> ControlledEntries:
            return self

        def __exit__(self, *args: object) -> None:
            del args
            self.closed = True

        def __iter__(self) -> ControlledEntries:
            return self

        def __next__(self) -> Path:
            self.next_calls += 1
            return Path(f"entry-{self.next_calls:05d}")

    entries = ControlledEntries()
    monkeypatch.setattr(os, "scandir", lambda path: entries)

    with pytest.raises(PdfCorpusError, match="inventory bound"):
        corpus_module._bounded_directory_names(
            tmp_path,
            maximum_entries=maximum_entries,
            excess_message="inventory bound exceeded",
        )

    assert entries.next_calls == expected_next_calls
    assert entries.closed


def test__bounded_directory_inventory__translates_open_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_open(path: os.PathLike[str] | str) -> None:
        del path
        raise PermissionError("injected directory-open failure")

    monkeypatch.setattr(os, "scandir", fail_open)

    with pytest.raises(PdfCorpusError, match="could not inspect"):
        corpus_module._bounded_directory_names(
            tmp_path,
            maximum_entries=1,
            excess_message="inventory bound exceeded",
        )


def test__page_inventory__accepts_canonical_ten_thousand_page_names() -> None:
    expected = (
        "page-0999.txt",
        "page-1000.txt",
        "page-1001.txt",
        "page-10000.txt",
    )
    actual = tuple(sorted(expected))
    assert actual != expected

    corpus_module._require_exact_inventory(
        actual,
        expected,
        "page artifact inventory is not canonical",
    )

    with pytest.raises(PdfCorpusError, match="inventory"):
        corpus_module._require_exact_inventory(
            actual[:-1],
            expected,
            "page artifact inventory is not canonical",
        )
