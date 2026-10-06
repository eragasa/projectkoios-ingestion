#!/Users/eugene/repos/projectkoios-ingestion/.venv/bin/python
from __future__ import annotations

import json
import os
from pathlib import Path

from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter

ROOT = Path(
    "/Users/eugene/projects/projectkoios/artifacts/reference-multimodal-preparation-v2/pix2tex-canary-v1"
)
CLASSIFICATIONS = {
    1: (
        "truncated_equation_region",
        "equation context is clipped above the retained region",
        True,
    ),
    2: ("clean_equation_region", None, False),
    3: (
        "equation_with_context_contamination",
        "prose from the following line enters the region",
        True,
    ),
    4: ("clean_equation_region", None, False),
    5: (
        "non_equation_or_overbroad_region",
        "a prose paragraph dominates the region",
        True,
    ),
    6: (
        "equation_with_context_contamination",
        "preceding prose and more than one mathematical expression enter the region",
        True,
    ),
    7: ("clean_equation_region", None, False),
    8: (
        "clean_equation_region",
        "recognition contains suspicious unmatched equation-label punctuation",
        True,
    ),
    9: ("clean_equation_region", None, False),
    10: (
        "non_equation_or_overbroad_region",
        "multiple numbered exercises, prose, and equations share the region",
        True,
    ),
    11: (
        "clean_equation_region",
        "recognition appears to confuse a subscript in the leading coefficient",
        True,
    ),
    12: ("clean_equation_region", None, False),
    13: (
        "equation_with_context_contamination",
        "following prose is clipped into the region",
        True,
    ),
    14: ("clean_equation_region", None, False),
    15: (
        "non_equation_or_overbroad_region",
        "table rows were detected as an equation",
        True,
    ),
    16: (
        "clean_equation_region",
        "recognition appears to substitute accent commands for partial derivatives",
        True,
    ),
    17: ("clean_equation_region", None, False),
    18: ("clean_equation_region", None, False),
    19: (
        "clean_equation_region",
        "recognition appears to substitute an intersection symbol for an integral",
        True,
    ),
    20: (
        "non_equation_or_overbroad_region",
        "symbol glossary rows were detected as an equation",
        True,
    ),
    21: (
        "truncated_equation_region",
        "surrounding prose and equation content are clipped",
        True,
    ),
    22: (
        "non_equation_or_overbroad_region",
        "prose and three equations share one region",
        True,
    ),
    23: (
        "equation_with_context_contamination",
        "preceding prose enters the region",
        True,
    ),
    24: (
        "equation_with_context_contamination",
        "prose above and below enters the region",
        True,
    ),
    25: (
        "non_equation_or_overbroad_region",
        "a prose sentence and display equation share the region",
        True,
    ),
    26: (
        "non_equation_or_overbroad_region",
        "a phonon diagram was detected as an equation",
        True,
    ),
    27: ("clean_equation_region", None, False),
    28: ("clean_equation_region", None, False),
    29: ("clean_equation_region", None, False),
    30: (
        "equation_with_context_contamination",
        "following prose enters the region",
        True,
    ),
}


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
    plan_bytes = exact(ROOT / "plan.json")
    inventory_bytes = exact(ROOT / "inventory.json")
    plan = json.loads(plan_bytes)
    inventory = json.loads(inventory_bytes)
    records = []
    for item in plan["items"]:
        sequence = item["sequence"]
        category, note, concern = CLASSIFICATIONS[sequence]
        result = json.loads(
            exact(ROOT / "results" / f"result-{sequence:03d}.json")
        )
        records.append(
            {
                "sequence": sequence,
                "book": item["book"],
                "page_index": item["page_index"],
                "assembly_id": item["assembly_id"],
                "region_category": category,
                "recognition_quality_concern": concern,
                "note": note,
                "proposal_status": result["recognition"]["proposals"][0][
                    "status"
                ],
                "accepted": False,
                "human_review_required": True,
            }
        )
    categories: dict[str, int] = {}
    for record in records:
        category = record["region_category"]
        categories[category] = categories.get(category, 0) + 1
    body = {
        "contract_version": "1.0",
        "audit_kind": "automated_visual_canary_audit",
        "canary_plan_id": plan["canary_plan_id"],
        "canary_inventory_id": inventory["canary_inventory_id"],
        "canary_plan_sha256": digest(plan_bytes),
        "canary_inventory_sha256": digest(inventory_bytes),
        "record_count": len(records),
        "region_category_counts": dict(sorted(categories.items())),
        "recognition_quality_concern_count": sum(
            record["recognition_quality_concern"] for record in records
        ),
        "operational_success_count": inventory["proposed_count"],
        "operational_failure_count": inventory["failed_count"],
        "accepted_count": 0,
        "human_review_required_count": len(records),
        "recommendation": "do_not_expand_queue_before_detector_crop_and_selection_policy_review",
        "records": records,
    }
    report = {
        **body,
        "audit_id": identity("reference-multimodal-pix2tex-canary-audit", body),
    }
    content = (
        json.dumps(
            report, ensure_ascii=False, indent=2, sort_keys=True
        ).encode()
        + b"\n"
    )
    path = ROOT / "automated-visual-audit.json"
    if path.exists():
        if exact(path) != content:
            raise RuntimeError("create-once audit differs")
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
                "audit_id": report["audit_id"],
                "audit_sha256": digest(content),
                "region_category_counts": report["region_category_counts"],
                "recognition_quality_concern_count": report[
                    "recognition_quality_concern_count"
                ],
                "operational_success_count": report[
                    "operational_success_count"
                ],
                "accepted_count": report["accepted_count"],
                "recommendation": report["recommendation"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
