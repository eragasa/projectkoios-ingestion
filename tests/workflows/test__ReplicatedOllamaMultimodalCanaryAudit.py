from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def load_workflow(repository_root: Path) -> ModuleType:
    path = (
        repository_root
        / "workflows/033.audit_replicated_ollama_multimodal_canary.py"
    )
    spec = importlib.util.spec_from_file_location(
        "replicated_ollama_multimodal_canary_audit_workflow",
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load replicated Ollama audit workflow")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test__replicated_ollama_audit__checks_exact_label_order(
    repository_root: Path,
) -> None:
    workflow = load_workflow(repository_root)

    exact = workflow.label_evaluation("c\nb\na")
    reordered = workflow.label_evaluation("a\nb\nc")

    assert exact["exact_multiset_match"] is True
    assert exact["exact_order_match"] is True
    assert reordered["exact_multiset_match"] is True
    assert reordered["exact_order_match"] is False


def test__replicated_ollama_audit__reports_missing_anchors_without_text(
    repository_root: Path,
) -> None:
    workflow = load_workflow(repository_root)

    evaluation = workflow.anchor_evaluation(
        "visible first and third",
        ("first", "second", "third"),
    )

    assert evaluation["expected_anchor_count"] == 3
    assert evaluation["observed_anchor_count"] == 2
    assert evaluation["missing_anchor_count"] == 1
    assert evaluation["all_anchors_observed"] is False
    assert evaluation["missing_anchor_sha256"] == [workflow.digest(b"second")]
    assert "second" not in evaluation.values()


def test__replicated_ollama_audit__retains_nondeterminism_limits(
    repository_root: Path,
) -> None:
    workflow = load_workflow(repository_root)

    assert workflow.EXPECTED_LINE_LABELS == ("c", "b", "a")
    assert len(workflow.TEXT_HEAVY_ANCHORS) == 4
    assert len(workflow.TABLE_ANCHORS) == 12
