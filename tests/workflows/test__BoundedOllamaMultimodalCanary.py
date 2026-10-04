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
        / "workflows/029.run_bounded_ollama_multimodal_canary.py"
    )
    spec = importlib.util.spec_from_file_location(
        "bounded_ollama_multimodal_canary_workflow",
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load bounded Ollama workflow")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test__bounded_ollama_canary__dry_run_never_invokes_model(
    repository_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = load_workflow(repository_root)
    output = tmp_path / "canary"
    plan = {
        "plan_id": "reference-ollama-multimodal-canary-plan:sha256:" + "a" * 64,
        "request_id": "ollama-multimodal-request:sha256:" + "b" * 64,
    }

    class Processor:
        def action(self, *, request: object) -> object:
            raise AssertionError(f"unexpected model invocation: {request!r}")

    monkeypatch.setattr(workflow, "OUTPUT", output)
    monkeypatch.setattr(
        workflow,
        "prepare",
        lambda: (plan, b"png evidence", object(), Processor()),
    )

    first = workflow.run(apply=False)
    replay = workflow.run(apply=False)

    assert first["model_execution_performed"] is False
    assert first["result_status"] == "not_requested"
    assert first["plan_status"] == "created"
    assert first["evidence_status"] == "created"
    assert replay["plan_status"] == "unchanged"
    assert replay["evidence_status"] == "unchanged"
    assert stat.S_IMODE(output.stat().st_mode) == 0o700
    assert stat.S_IMODE((output / "plan.json").stat().st_mode) == 0o600
    assert stat.S_IMODE((output / "evidence.png").stat().st_mode) == 0o600
    assert not (output / "result.json").exists()


def test__bounded_ollama_canary__apply_replays_without_model_invocation(
    repository_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = load_workflow(repository_root)
    output = tmp_path / "canary"
    plan = {
        "plan_id": "reference-ollama-multimodal-canary-plan:sha256:" + "a" * 64,
        "request_id": "ollama-multimodal-request:sha256:" + "b" * 64,
    }

    class Processor:
        def action(self, *, request: object) -> object:
            raise AssertionError(f"unexpected model invocation: {request!r}")

    monkeypatch.setattr(workflow, "OUTPUT", output)
    monkeypatch.setattr(
        workflow,
        "prepare",
        lambda: (plan, b"png evidence", object(), Processor()),
    )
    workflow.run(apply=False)
    result = {
        "request_id": plan["request_id"],
        "result_id": "ollama-multimodal-result:sha256:" + "c" * 64,
        "evidence_status": "automated_unreviewed",
        "determinism": "nondeterministic",
    }
    result_bytes = workflow.json_bytes(result)
    workflow.create_once(output / "result.json", result_bytes)
    summary_body = {
        "plan_id": plan["plan_id"],
        "request_id": plan["request_id"],
        "result_id": result["result_id"],
        "result_sha256": workflow.digest(result_bytes),
        "result_bytes": len(result_bytes),
        "processing_status": "complete",
        "cacheable": True,
    }
    summary = {
        **summary_body,
        "summary_id": workflow.identity(
            "reference-ollama-multimodal-canary-summary",
            summary_body,
        ),
    }
    workflow.create_once(output / "summary.json", workflow.json_bytes(summary))

    replay = workflow.run(apply=True)

    assert replay["model_execution_performed"] is False
    assert replay["result_status"] == "unchanged"
    assert replay["processing_status"] == "complete"


def test__bounded_ollama_canary__rejects_symlink_input(
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
