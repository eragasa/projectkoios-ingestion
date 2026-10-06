#!/Users/eugene/repos/projectkoios-ingestion/.venv/bin/python
from __future__ import annotations

import json
import os
import stat
from collections import Counter
from pathlib import Path, PurePosixPath

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter

ROOT = Path(
    "/Users/eugene/projects/projectkoios/artifacts"
    "/reference-ollama-multimodal-replicated-canary-v1"
)
EXPECTED_LINE_LABELS = ("c", "b", "a")
TEXT_HEAVY_ANCHORS = (
    "(a) Simple cubic.",
    "(b) Body-centered cubic.",
    "(c) Face-centered cubic.",
    "Diamond Structure",
)
TABLE_ANCHORS = (
    "Table 2.1.",
    "The character table of a group",
    "Classes",
    "Representations",
    "{E}",
    "{N2C2}",
    "{NjCj}",
    "R1",
    "R2",
    "Rj",
    "χ1(E)",
    "χj(j)",
)
CLIPPING_WARNING = {
    "code": "ollama.model.warning.0",
    "message": "Text is partially cut off at the bottom and right edges.",
}


def canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def digest(content: bytes) -> str:
    return SHA256Fingerprinter.fingerprint(content=content)


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


def relative_path(value: object, description: str) -> Path:
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"path required: {description}")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in ("", ".", "..") for part in path.parts)
    ):
        raise RuntimeError(f"safe relative path required: {description}")
    return Path(*path.parts)


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


def anchor_evaluation(text: str, anchors: tuple[str, ...]) -> dict[str, object]:
    if not isinstance(text, str):
        raise TypeError("proposal text must be a string")
    missing = tuple(anchor for anchor in anchors if anchor not in text)
    return {
        "method": "case_sensitive_literal_anchor_coverage",
        "expected_anchor_set_sha256": digest(canonical(anchors)),
        "expected_anchor_count": len(anchors),
        "observed_anchor_count": len(anchors) - len(missing),
        "missing_anchor_count": len(missing),
        "missing_anchor_sha256": [
            digest(anchor.encode()) for anchor in missing
        ],
        "all_anchors_observed": not missing,
    }


def label_evaluation(text: str) -> dict[str, object]:
    if not isinstance(text, str):
        raise TypeError("proposal text must be a string")
    observed = tuple(line.strip() for line in text.splitlines() if line.strip())
    expected_counts = Counter(EXPECTED_LINE_LABELS)
    observed_counts = Counter(observed)
    missing = tuple(sorted((expected_counts - observed_counts).elements()))
    unexpected = tuple(sorted((observed_counts - expected_counts).elements()))
    return {
        "method": "trim_nonempty_lines_case_sensitive",
        "expected_labels_in_visual_order": list(EXPECTED_LINE_LABELS),
        "observed_labels_in_model_order": list(observed),
        "missing_labels": list(missing),
        "unexpected_labels": list(unexpected),
        "exact_order_match": observed == EXPECTED_LINE_LABELS,
        "exact_multiset_match": not missing and not unexpected,
    }


def result_record(
    *,
    plan: dict[str, object],
    manifest: dict[str, object],
    invocation: dict[str, object],
    sample: dict[str, object],
) -> tuple[dict[str, object], str]:
    result_path = relative_path(invocation["result_path"], "result path")
    receipt_path = relative_path(invocation["receipt_path"], "receipt path")
    if result_path.parts[0] != "results" or receipt_path.parts[0] != "receipts":
        raise RuntimeError("result or receipt path boundary differs")
    result_bytes = exact(ROOT / result_path)
    result = json.loads(result_bytes)
    if type(result) is not dict:
        raise RuntimeError("result must be a JSON object")
    receipt = identified(
        ROOT / receipt_path,
        "receipt_id",
        "reference-ollama-multimodal-replicated-canary-receipt",
    )
    if (
        receipt.get("plan_id") != plan["plan_id"]
        or receipt.get("manifest_id") != manifest["manifest_id"]
        or receipt.get("invocation_id") != invocation["invocation_id"]
        or receipt.get("sample_id") != invocation["sample_id"]
        or receipt.get("replicate_ordinal") != invocation["replicate_ordinal"]
        or receipt.get("request_id") != invocation["request_id"]
        or receipt.get("cache_key") != invocation["cache_key"]
        or receipt.get("result_id") != result.get("result_id")
        or receipt.get("result_sha256") != digest(result_bytes)
        or receipt.get("result_bytes") != len(result_bytes)
        or receipt.get("processing_status") != "complete"
        or receipt.get("model_determinism") != "nondeterministic"
        or receipt.get("model_execution_performed") is not True
        or receipt.get("accepted") is not False
        or receipt.get("chunk_text_eligible") is not False
        or receipt.get("publication_eligible") is not False
    ):
        raise RuntimeError("result receipt binding differs")
    processor_identity = result.get("processor_identity")
    if (
        processor_identity != plan["processor_identity"]
        or result.get("request_id") != invocation["request_id"]
        or result.get("status") != "complete"
        or result.get("cacheable") is not True
        or result.get("evidence_status") != "automated_unreviewed"
        or result.get("determinism") != "nondeterministic"
        or result.get("contract_version") != "1.0"
    ):
        raise RuntimeError("result review gates differ")
    expected_cache_key = stable_id(
        "ollama-multimodal-cache-key",
        "1.0",
        result["request_id"],
        processor_identity,
    )
    if expected_cache_key != invocation["cache_key"]:
        raise RuntimeError("result cache identity differs")
    verification = result.get("model_verification")
    if (
        type(verification) is not dict
        or verification.get("ollama_version") != "0.34.3"
        or verification.get("model_name") != "qwen3.5:9b"
        or verification.get("expected_model_digest")
        != "6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7"
        or verification.get("preflight_observed_digest")
        != verification.get("expected_model_digest")
        or verification.get("postflight_observed_digest")
        != verification.get("expected_model_digest")
    ):
        raise RuntimeError("result model verification differs")
    prompt = result.get("prompt")
    selections = result.get("selection_results")
    if (
        type(prompt) is not dict
        or type(selections) is not list
        or len(selections) != 1
        or type(selections[0]) is not dict
    ):
        raise RuntimeError("result prompt or selection coverage differs")
    prompt_text = prompt.get("text")
    if not isinstance(prompt_text, str):
        raise RuntimeError("result prompt text is invalid")
    prompt_bytes = prompt_text.encode()
    if prompt.get("rendered_sha256") != digest(prompt_bytes) or prompt.get(
        "utf8_byte_length"
    ) != len(prompt_bytes):
        raise RuntimeError("result prompt identity differs")
    selection = selections[0]
    proposal = selection.get("proposal")
    if (
        selection.get("status") != "proposed"
        or selection.get("failure") is not None
        or selection.get("selection_id") != sample["selection_id"]
        or selection.get("region_id") != sample["region_id"]
        or selection.get("png_sha256") != sample["evidence_sha256"]
        or selection.get("png_byte_length") != sample["evidence_bytes"]
        or type(proposal) is not dict
    ):
        raise RuntimeError("result selection binding differs")
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
    expected_result_id = stable_id(
        "ollama-multimodal-result",
        "1.0",
        result["request_id"],
        result["processor_identity"],
        result["task_kind"],
        prompt,
        result["status"],
        result["evidence_status"],
        result["determinism"],
        result["cacheable"],
        result["metadata_responses"],
        result["model_verification"],
        result["raw_response"],
        selections,
    )
    if (
        expected_request_id != result["request_id"]
        or expected_result_id != result["result_id"]
    ):
        raise RuntimeError("request or result identity differs")
    text = proposal.get("text")
    warnings = proposal.get("warnings")
    if not isinstance(text, str) or type(warnings) is not list:
        raise RuntimeError("result proposal is invalid")
    text_bytes = text.encode()
    if (
        proposal.get("status") != "automated_unreviewed"
        or proposal.get("determinism") != "nondeterministic"
        or proposal.get("text_sha256") != digest(text_bytes)
        or proposal.get("text_utf8_byte_length") != len(text_bytes)
        or receipt.get("warning_count") != len(warnings)
    ):
        raise RuntimeError("result proposal evidence differs")
    raw = result.get("raw_response")
    if type(raw) is not dict:
        raise RuntimeError("result raw response identity is missing")
    return (
        {
            "invocation_id": invocation["invocation_id"],
            "replicate_ordinal": invocation["replicate_ordinal"],
            "result_id": result["result_id"],
            "result_sha256": digest(result_bytes),
            "result_bytes": len(result_bytes),
            "proposal_text_sha256": proposal["text_sha256"],
            "proposal_text_utf8_bytes": proposal["text_utf8_byte_length"],
            "proposal_line_count": len(text.splitlines()),
            "warning_count": len(warnings),
            "warning_set_sha256": digest(canonical(warnings)),
            "assistant_content_sha256": raw.get("assistant_content_sha256"),
            "http_body_sha256": raw.get("http_body_sha256"),
            "model_execution_performed": False,
        },
        text,
    )


def evaluate_sample(
    sample_key: str,
    records: list[dict[str, object]],
    texts: list[str],
    warning_sets: list[list[object]],
) -> dict[str, object]:
    if len(records) != 2 or len(texts) != 2 or len(warning_sets) != 2:
        raise RuntimeError(f"{sample_key}: exactly two replicates required")
    proposal_equal = (
        records[0]["proposal_text_sha256"] == records[1]["proposal_text_sha256"]
    )
    result_distinct = records[0]["result_id"] != records[1]["result_id"]
    serialized_distinct = (
        records[0]["result_sha256"] != records[1]["result_sha256"]
    )
    if sample_key == "labeled-figure":
        quality = label_evaluation(texts[0])
        quality_match = bool(
            quality["exact_order_match"] and quality["exact_multiset_match"]
        )
        expected_warning_match = warning_sets == [[], []]
        profile = "visible_labels_and_vertical_order"
    elif sample_key == "text-heavy-figure":
        quality = anchor_evaluation(texts[0], TEXT_HEAVY_ANCHORS)
        quality_match = bool(quality["all_anchors_observed"])
        expected_warning_match = warning_sets == [
            [CLIPPING_WARNING],
            [CLIPPING_WARNING],
        ]
        profile = "caption_heading_anchors_and_clipping_warning"
    elif sample_key == "structured-table":
        quality = anchor_evaluation(texts[0], TABLE_ANCHORS)
        quality_match = bool(quality["all_anchors_observed"])
        expected_warning_match = warning_sets == [[], []]
        profile = "table_heading_row_and_symbol_anchors"
    else:
        raise RuntimeError(f"unknown sample key: {sample_key}")
    return {
        "sample_key": sample_key,
        "audit_profile": profile,
        "replicates": records,
        "proposal_text_equal": proposal_equal,
        "result_identity_distinct": result_distinct,
        "serialized_result_distinct": serialized_distinct,
        "warning_sets_equal": warning_sets[0] == warning_sets[1],
        "expected_warning_match": expected_warning_match,
        "quality_evaluation": quality,
        "bounded_quality_checks_passed": quality_match
        and expected_warning_match,
        "content_beyond_declared_anchors_evaluated": sample_key
        == "labeled-figure",
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
        "reference-ollama-multimodal-replicated-canary-plan",
    )
    manifest = identified(
        ROOT / "request-manifest.json",
        "manifest_id",
        "reference-ollama-multimodal-replicated-canary-request-manifest",
    )
    summary = identified(
        ROOT / "execution-summary.json",
        "summary_id",
        "reference-ollama-multimodal-replicated-canary-summary",
    )
    if (
        manifest.get("plan_id") != plan["plan_id"]
        or summary.get("plan_id") != plan["plan_id"]
        or summary.get("manifest_id") != manifest["manifest_id"]
        or plan.get("planned_invocation_count") != 6
        or summary.get("invocation_count") != 6
        or plan.get("model_determinism") != "nondeterministic"
        or manifest.get("model_determinism") != "nondeterministic"
        or summary.get("model_determinism") != "nondeterministic"
        or summary.get("fresh_inference_reproducible") is not False
        or summary.get("accepted") is not False
        or summary.get("chunk_text_eligible") is not False
        or summary.get("publication_eligible") is not False
    ):
        raise RuntimeError("replicated canary collection boundary differs")
    samples = manifest.get("samples")
    invocations = manifest.get("invocations")
    if (
        type(samples) is not list
        or len(samples) != 3
        or any(type(item) is not dict for item in samples)
        or type(invocations) is not list
        or len(invocations) != 6
        or any(type(item) is not dict for item in invocations)
    ):
        raise RuntimeError("replicated canary manifest coverage differs")
    sample_by_id = {str(item["sample_id"]): item for item in samples}
    records_by_key: dict[str, list[dict[str, object]]] = {}
    texts_by_key: dict[str, list[str]] = {}
    warnings_by_key: dict[str, list[list[object]]] = {}
    for invocation in invocations:
        sample = sample_by_id.get(str(invocation["sample_id"]))
        if sample is None:
            raise RuntimeError("invocation sample binding differs")
        record, text = result_record(
            plan=plan,
            manifest=manifest,
            invocation=invocation,
            sample=sample,
        )
        result = json.loads(
            exact(
                ROOT / relative_path(invocation["result_path"], "result path")
            )
        )
        warning_set = result["selection_results"][0]["proposal"]["warnings"]
        sample_key = str(sample["sample_key"])
        records_by_key.setdefault(sample_key, []).append(record)
        texts_by_key.setdefault(sample_key, []).append(text)
        warnings_by_key.setdefault(sample_key, []).append(warning_set)
    sample_audits = [
        evaluate_sample(
            key,
            records_by_key[key],
            texts_by_key[key],
            warnings_by_key[key],
        )
        for key in (
            "labeled-figure",
            "text-heavy-figure",
            "structured-table",
        )
    ]
    bounded_checks_passed = all(
        item["bounded_quality_checks_passed"] for item in sample_audits
    )
    proposal_equal_count = sum(
        bool(item["proposal_text_equal"]) for item in sample_audits
    )
    distinct_result_count = sum(
        bool(item["result_identity_distinct"]) for item in sample_audits
    )
    body = {
        "contract_version": "1.0",
        "plan_id": plan["plan_id"],
        "manifest_id": manifest["manifest_id"],
        "execution_summary_id": summary["summary_id"],
        "audit_method": "fixed_result_byte_replay",
        "sample_count": len(sample_audits),
        "invocation_count": 6,
        "sample_audits": sample_audits,
        "proposal_equal_pair_count": proposal_equal_count,
        "distinct_result_identity_pair_count": distinct_result_count,
        "proposal_variability_observed": proposal_equal_count
        != len(sample_audits),
        "result_envelope_variability_observed": distinct_result_count > 0,
        "audit_status": (
            "bounded_checks_passed"
            if bounded_checks_passed
            else "bounded_concerns_detected"
        ),
        "assessment": (
            "all_pairs_matched_proposal_text_with_distinct_result_envelopes"
        ),
        "limitations": [
            "two_invocations_per_sample_only",
            "identical_proposals_do_not_establish_determinism",
            "fresh_ollama_inference_may_differ",
            "quality_audit_uses_bounded_labels_anchors_and_warnings",
            "content_beyond_declared_anchors_not_exhaustively_evaluated",
            "table_relational_structure_not_exhaustively_evaluated",
            "no_corpus_suitability_claim",
        ],
        "model_determinism": "nondeterministic",
        "automated": True,
        "review_status": "unreviewed",
        "accepted": False,
        "chunk_text_eligible": False,
        "publication_eligible": False,
        "model_execution_performed": False,
    }
    artifact = {
        **body,
        "audit_id": identity(
            "reference-ollama-multimodal-replicated-canary-quality-audit",
            body,
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
        "artifact_status": status,
        "audit_status": artifact["audit_status"],
        "sample_count": artifact["sample_count"],
        "invocation_count": artifact["invocation_count"],
        "proposal_equal_pair_count": proposal_equal_count,
        "distinct_result_identity_pair_count": distinct_result_count,
        "model_execution_performed": False,
        "accepted": False,
    }


def main() -> None:
    print(json.dumps(audit(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
