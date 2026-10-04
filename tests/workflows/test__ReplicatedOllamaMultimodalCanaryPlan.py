from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def load_workflow(repository_root: Path) -> ModuleType:
    path = (
        repository_root
        / "workflows/031.plan_replicated_ollama_multimodal_canary.py"
    )
    spec = importlib.util.spec_from_file_location(
        "replicated_ollama_multimodal_canary_plan_workflow",
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load replicated Ollama plan workflow")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test__replicated_ollama_plan__creates_two_independent_slots_per_sample(
    repository_root: Path,
) -> None:
    workflow = load_workflow(repository_root)
    samples = [
        {"sample_id": f"sample:{index}", "sample_key": f"sample-{index}"}
        for index in range(3)
    ]
    processor = {"processor_name": "fixture"}

    invocations = workflow.replicated_invocations(samples, processor)

    assert len(invocations) == 6
    assert len({item["invocation_id"] for item in invocations}) == 6
    assert [item["replicate_ordinal"] for item in invocations] == [
        1,
        2,
        1,
        2,
        1,
        2,
    ]
    assert all(
        item["execution_status"] == "not_requested" for item in invocations
    )
    assert all(
        item["cache_policy"]
        == "independent_invocation_no_cross_replicate_reuse"
        for item in invocations
    )


def test__replicated_ollama_plan__retains_nondeterminism_boundary(
    repository_root: Path,
) -> None:
    workflow = load_workflow(repository_root)

    assert workflow.REPLICATES_PER_SAMPLE == 2
    assert {sample.evidence_class for sample in workflow.SAMPLES} == {
        "figure",
        "table",
    }
    assert [sample.sample_key for sample in workflow.SAMPLES] == [
        "labeled-figure",
        "text-heavy-figure",
        "structured-table",
    ]
