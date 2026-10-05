from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def load_workflow(repository_root: Path) -> ModuleType:
    path = (
        repository_root
        / "workflows/034.plan_mixed_native_ocr_reconciliation_reassessment.py"
    )
    spec = importlib.util.spec_from_file_location(
        "mixed_native_ocr_reconciliation_reassessment_workflow",
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load mixed-native reassessment workflow")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def candidate(
    workflow: ModuleType,
    *,
    source: str,
    page_index: int,
    native_bytes: int,
) -> object:
    return workflow.Candidate(
        source_sha256=source,
        source_id=f"source:{source}",
        source_blob_id=f"blob:sha256:{source}",
        source_byte_size=100,
        extraction_path=Path(f"{source}/extraction.json"),
        extraction_sha256="e" * 64,
        extraction_bytes=200,
        document_id=f"document:{source}",
        manifest_id=f"manifest:{source}",
        page_index=page_index,
        native_text_utf8_bytes=native_bytes,
        native_text_sha256="t" * 64,
        native_text_block_ids=(f"block:{page_index}",),
    )


def test__mixed_native_reassessment__selects_maximum_text_per_source(
    repository_root: Path,
) -> None:
    workflow = load_workflow(repository_root)
    source_a = "a" * 64
    source_b = "b" * 64
    values = (
        candidate(workflow, source=source_a, page_index=8, native_bytes=10),
        candidate(workflow, source=source_a, page_index=4, native_bytes=30),
        candidate(workflow, source=source_b, page_index=2, native_bytes=20),
    )

    selected = workflow.select_candidates(values)

    assert [(item.source_sha256, item.page_index) for item in selected] == [
        (source_a, 4),
        (source_b, 2),
    ]


def test__mixed_native_reassessment__breaks_ties_by_lowest_page(
    repository_root: Path,
) -> None:
    workflow = load_workflow(repository_root)
    source = "c" * 64
    values = (
        candidate(workflow, source=source, page_index=9, native_bytes=30),
        candidate(workflow, source=source, page_index=3, native_bytes=30),
    )

    selected = workflow.select_candidates(values)

    assert len(selected) == 1
    assert selected[0].page_index == 3


def test__mixed_native_reassessment__retains_plan_only_boundary(
    repository_root: Path,
) -> None:
    workflow = load_workflow(repository_root)

    assert workflow.LOW_TEXT_UTF8_LIMIT == 40
    assert workflow.EXPECTED_MIXED_LOW_TEXT_PAGES == 40
    assert workflow.EXPECTED_MIXED_LOW_TEXT_DOCUMENTS == 5


def test__mixed_native_reassessment__create_once_is_private_and_replay_safe(
    repository_root: Path,
    tmp_path: Path,
) -> None:
    workflow = load_workflow(repository_root)
    artifact = tmp_path / "private" / "plan.json"

    assert workflow.create_once(artifact, b"exact\n") == "created"
    assert artifact.stat().st_mode & 0o777 == 0o600
    original_time = artifact.stat().st_mtime_ns
    assert workflow.create_once(artifact, b"exact\n") == "unchanged"
    assert artifact.stat().st_mtime_ns == original_time


def test__mixed_native_reassessment__rejects_changed_create_once_bytes(
    repository_root: Path,
    tmp_path: Path,
) -> None:
    workflow = load_workflow(repository_root)
    artifact = tmp_path / "private" / "plan.json"
    workflow.create_once(artifact, b"exact\n")

    try:
        workflow.create_once(artifact, b"different\n")
    except RuntimeError as error:
        assert "create-once artifact differs" in str(error)
    else:
        raise AssertionError("changed create-once content must be rejected")
