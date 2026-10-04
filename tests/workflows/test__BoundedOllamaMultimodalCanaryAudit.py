from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def load_workflow(repository_root: Path) -> ModuleType:
    path = (
        repository_root
        / "workflows/030.audit_bounded_ollama_multimodal_canary.py"
    )
    spec = importlib.util.spec_from_file_location(
        "bounded_ollama_multimodal_canary_audit_workflow",
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load bounded Ollama audit workflow")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test__bounded_ollama_audit__matches_spatial_labels_without_order_claim(
    repository_root: Path,
) -> None:
    workflow = load_workflow(repository_root)

    result = workflow.evaluate_labels("c\nb\na")

    assert result == {
        "normalization": "trim_nonempty_lines_case_sensitive",
        "expected_labels": ["a", "b", "c"],
        "observed_labels_in_model_order": ["c", "b", "a"],
        "missing_labels": [],
        "unexpected_labels": [],
        "duplicated_labels": [],
        "exact_label_multiset_match": True,
    }


def test__bounded_ollama_audit__reports_missing_and_invented_labels(
    repository_root: Path,
) -> None:
    workflow = load_workflow(repository_root)

    result = workflow.evaluate_labels("a\na\nd")

    assert result["missing_labels"] == ["b", "c"]
    assert result["unexpected_labels"] == ["a", "d"]
    assert result["duplicated_labels"] == ["a"]
    assert result["exact_label_multiset_match"] is False
