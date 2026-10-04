from __future__ import annotations

import importlib.util
import stat
import sys
from pathlib import Path
from types import ModuleType

import pytest


def load_workflow(repository_root: Path) -> ModuleType:
    path = (
        repository_root
        / "workflows/032.execute_replicated_ollama_multimodal_canary.py"
    )
    spec = importlib.util.spec_from_file_location(
        "replicated_ollama_multimodal_canary_execution_workflow",
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load replicated Ollama execution workflow")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def prepared_fixture(workflow: ModuleType) -> tuple[object, ...]:
    plan_id = (
        "reference-ollama-multimodal-replicated-canary-plan:sha256:" + "a" * 64
    )
    plan = {"plan_id": plan_id}
    invocations = []
    prepared = {}
    for ordinal in (1, 2):
        sample_id = "sample:fixture"
        invocation_id = f"invocation:{ordinal}"
        invocations.append(
            {
                "invocation_id": invocation_id,
                "sample_id": sample_id,
                "sample_key": "fixture",
                "replicate_ordinal": ordinal,
                "request_id": "request:fixture",
                "cache_key": "cache:fixture",
                "result_path": f"results/fixture-{ordinal}.json",
                "receipt_path": f"receipts/fixture-{ordinal}.json",
            }
        )
        prepared[sample_id] = workflow.PreparedSample(
            sample_id=sample_id,
            sample_key="fixture",
            request=object(),
            cache_key="cache:fixture",
            region_id="region:fixture",
            selection_id="selection:fixture",
        )
    manifest = {
        "manifest_id": "manifest:fixture",
        "invocations": invocations,
    }

    class Processor:
        def action(self, *, request: object) -> object:
            raise AssertionError(f"unexpected model invocation: {request!r}")

    return plan, manifest, prepared, Processor()


def test__replicated_ollama_execution__dry_run_never_invokes_model(
    repository_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = load_workflow(repository_root)
    output = tmp_path / "replicated-canary"
    prepared = prepared_fixture(workflow)
    monkeypatch.setattr(workflow, "OUTPUT", output)
    monkeypatch.setattr(workflow, "prepare", lambda: prepared)

    first = workflow.run(apply_plan_id=None)
    replay = workflow.run(apply_plan_id=None)

    assert first["model_executions_performed"] == 0
    assert first["execution_requested"] is False
    assert first["retained_result_count"] == 0
    assert set(first["invocation_statuses"].values()) == {"not_requested"}
    assert first["manifest_status"] == "created"
    assert replay["manifest_status"] == "unchanged"
    assert stat.S_IMODE(output.stat().st_mode) == 0o700
    assert (
        stat.S_IMODE((output / "request-manifest.json").stat().st_mode) == 0o600
    )
    assert not (output / "results").exists()


def test__replicated_execution__rejects_wrong_apply_id_before_action(
    repository_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = load_workflow(repository_root)
    monkeypatch.setattr(workflow, "OUTPUT", tmp_path / "replicated-canary")
    monkeypatch.setattr(
        workflow,
        "prepare",
        lambda: prepared_fixture(workflow),
    )

    with pytest.raises(RuntimeError, match="plan identity differs"):
        workflow.run(apply_plan_id="wrong-plan")


def test__replicated_ollama_execution__rejects_symlink_input(
    repository_root: Path,
    tmp_path: Path,
) -> None:
    workflow = load_workflow(repository_root)
    target = tmp_path / "target"
    target.write_bytes(b"private")
    target.chmod(0o600)
    link = tmp_path / "link"
    link.symlink_to(target)

    with pytest.raises(RuntimeError, match="missing or unsafe"):
        workflow.exact(link)
