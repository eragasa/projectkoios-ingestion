#!/Users/eugene/repos/projectkoios-ingestion/.venv/bin/python
from __future__ import annotations

import hashlib
import json
import os
import stat
from collections import Counter
from pathlib import Path

from projectkoios.ingestion.identity import stable_id

ROOT = Path(
    "/Users/eugene/projects/projectkoios/artifacts"
    "/reference-ollama-multimodal-canary-v1"
)
EXPECTED_LABELS = ("a", "b", "c")
EXPECTED_EVIDENCE_SHA256 = (
    "7148b85feda98a752f50418bca793196ff3c7674c223ee5e1c5e0253f8b7d739"
)
EXPECTED_EVIDENCE_BYTES = 20_272


def canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def identity(namespace: str, value: object) -> str:
    return f"{namespace}:sha256:{digest(canonical(value))}"


def exact(path: Path) -> bytes:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise RuntimeError(f"missing or unsafe file: {path}") from error
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise RuntimeError(f"missing or unsafe file: {path}")
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise RuntimeError(f"file is not private: {path}")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            content = stream.read()
        if len(content) != metadata.st_size:
            raise RuntimeError(f"file changed while reading: {path}")
        return content
    finally:
        os.close(descriptor)


def identified(path: Path, key: str, namespace: str) -> dict[str, object]:
    value = json.loads(exact(path))
    if type(value) is not dict:
        raise RuntimeError(f"JSON object required: {path}")
    body = dict(value)
    observed = body.pop(key, None)
    if observed != identity(namespace, body):
        raise RuntimeError(f"identity differs: {path}")
    return value


def create_once(path: Path, content: bytes) -> str:
    if path.exists():
        if exact(path) != content:
            raise RuntimeError(f"create-once artifact differs: {path}")
        return "unchanged"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    return "created"


def evaluate_labels(text: str) -> dict[str, object]:
    if type(text) is not str:
        raise TypeError("proposal text must be a string")
    observed = tuple(line.strip() for line in text.splitlines() if line.strip())
    expected_counts = Counter(EXPECTED_LABELS)
    observed_counts = Counter(observed)
    missing = tuple(sorted((expected_counts - observed_counts).elements()))
    unexpected = tuple(sorted((observed_counts - expected_counts).elements()))
    duplicates = tuple(
        sorted(token for token, count in observed_counts.items() if count > 1)
    )
    return {
        "normalization": "trim_nonempty_lines_case_sensitive",
        "expected_labels": list(EXPECTED_LABELS),
        "observed_labels_in_model_order": list(observed),
        "missing_labels": list(missing),
        "unexpected_labels": list(unexpected),
        "duplicated_labels": list(duplicates),
        "exact_label_multiset_match": not missing and not unexpected,
    }


def audit() -> dict[str, object]:
    os.umask(0o077)
    if ROOT.is_symlink() or not ROOT.is_dir():
        raise RuntimeError(f"missing or unsafe canary root: {ROOT}")
    if stat.S_IMODE(ROOT.stat().st_mode) & 0o077:
        raise RuntimeError(f"canary root is not private: {ROOT}")

    plan = identified(
        ROOT / "plan.json",
        "plan_id",
        "reference-ollama-multimodal-canary-plan",
    )
    summary = identified(
        ROOT / "summary.json",
        "summary_id",
        "reference-ollama-multimodal-canary-summary",
    )
    evidence = exact(ROOT / "evidence.png")
    result_bytes = exact(ROOT / "result.json")
    result = json.loads(result_bytes)
    if type(result) is not dict:
        raise RuntimeError("canary result must be a JSON object")
    if (
        len(evidence) != EXPECTED_EVIDENCE_BYTES
        or digest(evidence) != EXPECTED_EVIDENCE_SHA256
        or plan["evidence_bytes"] != len(evidence)
        or plan["evidence_sha256"] != digest(evidence)
    ):
        raise RuntimeError("canary evidence differs")
    if (
        summary["plan_id"] != plan["plan_id"]
        or summary["request_id"] != plan["request_id"]
        or summary["result_id"] != result.get("result_id")
        or summary["result_sha256"] != digest(result_bytes)
        or summary["result_bytes"] != len(result_bytes)
        or summary["processing_status"] != "complete"
        or summary["cacheable"] is not True
        or summary["accepted"] is not False
        or summary["chunk_text_eligible"] is not False
        or summary["publication_eligible"] is not False
    ):
        raise RuntimeError("canary summary binding differs")
    processor_identity = result.get("processor_identity")
    if (
        processor_identity != plan["processor_identity"]
        or result.get("request_id") != plan["request_id"]
        or result.get("status") != "complete"
        or result.get("cacheable") is not True
        or result.get("evidence_status") != "automated_unreviewed"
        or result.get("determinism") != "nondeterministic"
    ):
        raise RuntimeError("canary result gates differ")
    expected_cache_key = stable_id(
        "ollama-multimodal-cache-key",
        "1.0",
        result["request_id"],
        processor_identity,
    )
    if plan["cache_key"] != expected_cache_key:
        raise RuntimeError("canary cache identity differs")

    prompt = result.get("prompt")
    selection_results = result.get("selection_results")
    if type(prompt) is not dict or type(selection_results) is not list:
        raise RuntimeError("canary request evidence is invalid")
    prompt_text = prompt.get("text")
    if type(prompt_text) is not str:
        raise RuntimeError("canary prompt text is invalid")
    prompt_bytes = prompt_text.encode()
    if (
        prompt.get("rendered_sha256") != digest(prompt_bytes)
        or prompt.get("utf8_byte_length") != len(prompt_bytes)
        or len(selection_results) != 1
        or type(selection_results[0]) is not dict
    ):
        raise RuntimeError("canary prompt or selection coverage differs")
    selection = selection_results[0]
    identity_values = [
        selection[key]
        for key in (
            "selection_id",
            "source_id",
            "source_blob_id",
            "source_content_hash",
            "page_index",
            "region_id",
            "png_sha256",
            "png_byte_length",
            "width_pixels",
            "height_pixels",
        )
    ]
    expected_request_id = stable_id(
        "ollama-multimodal-request",
        "1.0",
        result["task_kind"],
        [identity_values],
        prompt,
    )
    if expected_request_id != result["request_id"]:
        raise RuntimeError("canary request identity differs")
    if (
        selection.get("status") != "proposed"
        or selection.get("failure") is not None
        or selection.get("png_sha256") != EXPECTED_EVIDENCE_SHA256
        or selection.get("png_byte_length") != EXPECTED_EVIDENCE_BYTES
    ):
        raise RuntimeError("canary selection result differs")
    proposal = selection.get("proposal")
    if type(proposal) is not dict:
        raise RuntimeError("canary proposal is missing")
    proposal_text = proposal.get("text")
    if type(proposal_text) is not str:
        raise RuntimeError("canary proposal text is invalid")
    proposal_bytes = proposal_text.encode()
    warnings = proposal.get("warnings")
    if (
        proposal.get("status") != "automated_unreviewed"
        or proposal.get("determinism") != "nondeterministic"
        or proposal.get("text_sha256") != digest(proposal_bytes)
        or proposal.get("text_utf8_byte_length") != len(proposal_bytes)
        or type(warnings) is not list
    ):
        raise RuntimeError("canary proposal evidence differs")

    label_evaluation = evaluate_labels(proposal_text)
    observed_labels = label_evaluation.get("observed_labels_in_model_order")
    missing_labels = label_evaluation.get("missing_labels")
    unexpected_labels = label_evaluation.get("unexpected_labels")
    if (
        type(observed_labels) is not list
        or type(missing_labels) is not list
        or type(unexpected_labels) is not list
    ):
        raise RuntimeError("label evaluation coverage is invalid")
    passed = bool(label_evaluation["exact_label_multiset_match"])
    audit_body = {
        "contract_version": "1.0",
        "plan_id": plan["plan_id"],
        "request_id": result["request_id"],
        "result_id": result["result_id"],
        "result_sha256": digest(result_bytes),
        "summary_id": summary["summary_id"],
        "evidence_sha256": digest(evidence),
        "proposal_text_sha256": proposal["text_sha256"],
        "adapter_warning_count": len(warnings),
        "model_determinism": "nondeterministic",
        "audit_method": "fixed_result_byte_replay",
        "label_evaluation": label_evaluation,
        "audit_status": "passed" if passed else "concerns_detected",
        "assessment": (
            "bounded_visible_label_coverage_consistent"
            if passed
            else "bounded_visible_label_coverage_concerns"
        ),
        "limitations": [
            "single_nondeterministic_invocation_only",
            "rerunning_ollama_may_produce_different_output",
            "single_clear_diagram_sample",
            "label_coverage_only",
            "diagram_relationships_not_evaluated",
            "reading_order_not_evaluated_for_spatial_labels",
            "adapter_warning_absence_does_not_establish_quality",
            "no_corpus_suitability_claim",
        ],
        "automated": True,
        "review_status": "unreviewed",
        "accepted": False,
        "chunk_text_eligible": False,
        "publication_eligible": False,
        "model_execution_performed": False,
    }
    artifact = {
        **audit_body,
        "audit_id": identity(
            "reference-ollama-multimodal-canary-quality-audit",
            audit_body,
        ),
    }
    content = (
        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode()
    status = create_once(ROOT / "quality-audit-v1.json", content)
    return {
        "audit_id": artifact["audit_id"],
        "audit_sha256": digest(content),
        "audit_bytes": len(content),
        "audit_status": artifact["audit_status"],
        "artifact_status": status,
        "expected_label_count": len(EXPECTED_LABELS),
        "observed_label_count": len(observed_labels),
        "missing_label_count": len(missing_labels),
        "unexpected_label_count": len(unexpected_labels),
        "model_execution_performed": False,
        "accepted": False,
    }


def main() -> None:
    print(json.dumps(audit(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
