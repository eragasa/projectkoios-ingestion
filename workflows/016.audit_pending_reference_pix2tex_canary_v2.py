#!/Users/eugene/repos/projectkoios-ingestion/.venv/bin/python
from __future__ import annotations

import json
import os
from pathlib import Path

from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter

ROOT = Path(
    "/Users/eugene/projects/projectkoios/artifacts/reference-multimodal-preparation-v2/pix2tex-canary-v2"
)
CLASSIFICATIONS = {
    1: ("clean_equation_region", None, False),
    2: ("clean_equation_region", None, False),
    3: (
        "clean_equation_region",
        "recognition appears to substitute another symbol for the identity",
        True,
    ),
    4: ("clean_equation_region", None, False),
    5: ("clean_equation_region", None, False),
    6: ("clean_equation_region", None, False),
    7: ("clean_equation_region", None, False),
    8: (
        "clean_equation_region",
        "recognition contains suspicious unmatched equation-label punctuation",
        True,
    ),
    9: ("clean_equation_region", None, False),
    10: ("clean_equation_region", None, False),
    11: (
        "clean_equation_region",
        "recognition appears to confuse the leading coefficient and subscripts",
        True,
    ),
    12: (
        "clean_equation_region",
        "recognition contains an extreme run of spacing commands",
        True,
    ),
    13: (
        "truncated_equation_region",
        "the left-hand relation appears incomplete",
        True,
    ),
    14: (
        "clean_equation_region",
        "recognition structure does not match the boxed expression",
        True,
    ),
    15: (
        "clean_equation_region",
        "recognition loses the equality between absolute-value terms",
        True,
    ),
    16: (
        "clean_equation_region",
        "recognition does not preserve the displayed fraction structure",
        True,
    ),
    17: ("clean_equation_region", None, False),
    18: ("clean_equation_region", None, False),
    19: (
        "clean_equation_region",
        "recognition appears to substitute the boundary subscript",
        True,
    ),
    20: (
        "clean_equation_region",
        "recognition adds a square root and changes exponents",
        True,
    ),
    21: (
        "clean_equation_region",
        "recognition substantially differs from the displayed equation",
        True,
    ),
    22: ("clean_equation_region", None, False),
    23: ("clean_equation_region", None, False),
    24: (
        "clean_equation_region",
        "recognition introduces a malformed fraction",
        True,
    ),
    25: ("clean_equation_region", None, False),
    26: ("clean_equation_region", None, False),
    27: (
        "non_equation_or_overbroad_region",
        "an annotated vector diagram was selected as an equation",
        True,
    ),
    28: ("clean_equation_region", None, False),
    29: ("clean_equation_region", None, False),
    30: (
        "clean_equation_region",
        "recognition changes gamma and duplicates the equation label",
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
        "recommendation": "region_quality_target_met_but_do_not_expand_before_recognition_output_policy_review",
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
