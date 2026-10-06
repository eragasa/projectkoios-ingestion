#!/Users/eugene/repos/projectkoios-ingestion/.venv/bin/python
from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path

from projectkoios.ingestion.integrations.pix2tex.output_policy import (
    pix2tex_output_quality_warning_codes,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter

ROOT = Path(
    "/Users/eugene/projects/projectkoios/artifacts/reference-multimodal-preparation-v2"
)
CANARIES = ("pix2tex-canary-v1", "pix2tex-canary-v2")


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()


def digest(content: bytes) -> str:
    return SHA256Fingerprinter.fingerprint(content=content)


def identity(namespace: str, value: object) -> str:
    return f"{namespace}:sha256:{digest(canonical(value))}"


def exact(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"missing or unsafe file: {path}")
    return path.read_bytes()


def main() -> None:
    source_labels = {}
    for path in ROOT.glob("books/*/chunks/chunk-*/quality-inventory.json"):
        value = json.loads(exact(path))
        for assembly in value["equation_assemblies"]:
            source_labels[assembly["assembly_id"]] = tuple(
                assembly["source_labels"]
            )
    records = []
    source_artifacts = []
    warning_counts: Counter[str] = Counter()
    canary_summaries = []
    for name in CANARIES:
        canary = ROOT / name
        plan_bytes = exact(canary / "plan.json")
        inventory_bytes = exact(canary / "inventory.json")
        audit_bytes = exact(canary / "automated-visual-audit.json")
        plan = json.loads(plan_bytes)
        inventory = json.loads(inventory_bytes)
        audit = json.loads(audit_bytes)
        source_artifacts.append(
            {
                "canary": name,
                "plan_id": plan["canary_plan_id"],
                "plan_sha256": digest(plan_bytes),
                "inventory_id": inventory["canary_inventory_id"],
                "inventory_sha256": digest(inventory_bytes),
                "audit_id": audit["audit_id"],
                "audit_sha256": digest(audit_bytes),
            }
        )
        concerns = {
            record["sequence"]: record["recognition_quality_concern"]
            for record in audit["records"]
        }
        confusion = Counter()
        for item in plan["items"]:
            sequence = item["sequence"]
            path = canary / "results" / f"result-{sequence:03d}.json"
            result_bytes = exact(path)
            result = json.loads(result_bytes)
            proposal = result["recognition"]["proposals"][0]
            latex = proposal["latex"]["latex"]
            warnings = list(
                pix2tex_output_quality_warning_codes(
                    latex,
                    item["sanitized_native_text"],
                    source_labels[item["assembly_id"]],
                )
            )
            if proposal["mathml"] is None:
                warnings.append("mathml_conversion_unavailable")
            warnings = tuple(warnings)
            warning_counts.update(warnings)
            detected = bool(warnings)
            concern = concerns[sequence]
            if detected and concern:
                outcome = "detected_concern"
            elif detected:
                outcome = "warning_without_audited_concern"
            elif concern:
                outcome = "undetected_semantic_or_visual_concern"
            else:
                outcome = "no_warning_no_audited_concern"
            confusion[outcome] += 1
            records.append(
                {
                    "canary": name,
                    "sequence": sequence,
                    "assembly_id": item["assembly_id"],
                    "proposal_id": proposal["proposal_id"],
                    "result_sha256": digest(result_bytes),
                    "quality_warning_codes": list(warnings),
                    "automated_audit_concern": concern,
                    "comparison_outcome": outcome,
                    "accepted": False,
                    "human_review_required": True,
                }
            )
        canary_summaries.append(
            {
                "canary": name,
                "record_count": len(plan["items"]),
                "comparison_counts": dict(sorted(confusion.items())),
            }
        )
    totals = Counter(record["comparison_outcome"] for record in records)
    detected = totals["detected_concern"]
    warning_total = detected + totals["warning_without_audited_concern"]
    concern_total = detected + totals["undetected_semantic_or_visual_concern"]
    superseded_bytes = exact(ROOT / "pix2tex-output-quality-audit-v4.json")
    superseded = json.loads(superseded_bytes)
    body = {
        "contract_version": "1.0",
        "policy_version": "pix2tex-output-quality-5",
        "supersedes_output_quality_audit_id": superseded[
            "output_quality_audit_id"
        ],
        "supersedes_output_quality_audit_sha256": digest(superseded_bytes),
        "source_artifacts": source_artifacts,
        "record_count": len(records),
        "records": records,
        "warning_counts": dict(sorted(warning_counts.items())),
        "comparison_counts": dict(sorted(totals.items())),
        "canary_summaries": canary_summaries,
        "observed_warning_precision": detected / warning_total,
        "observed_concern_recall": detected / concern_total,
        "accepted_count": 0,
        "human_review_required_count": len(records),
        "recommendation": "pix2tex_unsuitable_for_unattended_queue_execution_defer_eligible_queue",
        "limitations": [
            "automated_visual_audit_is_not_human_acceptance",
            "semantic_symbol_substitutions_are_not_deterministically_detectable",
            "warnings_do_not_validate_mathematical_correctness",
        ],
    }
    value = {
        **body,
        "output_quality_audit_id": identity(
            "reference-multimodal-pix2tex-output-quality-audit", body
        ),
    }
    content = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode()
        + b"\n"
    )
    path = ROOT / "pix2tex-output-quality-audit-v5.json"
    if path.exists():
        if exact(path) != content:
            raise RuntimeError("create-once output-quality audit differs")
        status = "unchanged"
    else:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        status = "created"
    print(
        json.dumps(
            {
                "status": status,
                "output_quality_audit_id": value["output_quality_audit_id"],
                "output_quality_audit_sha256": digest(content),
                "record_count": value["record_count"],
                "warning_counts": value["warning_counts"],
                "comparison_counts": value["comparison_counts"],
                "canary_summaries": value["canary_summaries"],
                "observed_warning_precision": value[
                    "observed_warning_precision"
                ],
                "observed_concern_recall": value["observed_concern_recall"],
                "recommendation": value["recommendation"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
