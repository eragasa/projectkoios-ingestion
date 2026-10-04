#!/Users/eugene/repos/projectkoios-ingestion/.venv/bin/python
from __future__ import annotations

import hashlib
import json
import os
import runpy
from pathlib import Path

ROOT = Path(
    "/Users/eugene/projects/projectkoios/artifacts/reference-multimodal-preparation-v2"
)
POLICY_SCRIPT = (
    Path(__file__).resolve().parent
    / "015.run_pending_reference_pix2tex_canary_v2.py"
)


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def identity(namespace: str, value: object) -> str:
    return f"{namespace}:sha256:{digest(canonical(value))}"


def exact(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"missing or unsafe file: {path}")
    return path.read_bytes()


def disposition(features: dict[str, object]) -> str:
    reasons = set(features["reasons"])
    if features["eligible"]:
        return "proposed_isolated_equation"
    if int(features["native_text_characters"]) < 4:
        if (
            float(features["top_ink_margin_fraction"]) < 0.02
            or float(features["bottom_ink_margin_fraction"]) < 0.02
        ):
            return "retained_truncated_region"
        return "retained_non_equation_visual"
    if "two_band_region_touches_vertical_edge" in reasons:
        return "retained_context_contaminated"
    return "retained_overbroad_region"


def main() -> None:
    eligibility = runpy.run_path(str(POLICY_SCRIPT))["eligibility"]
    proposed_bytes = exact(ROOT / "proposed-primary-recognition-inventory.json")
    proposed = json.loads(proposed_bytes)
    records = []
    counts: dict[str, int] = {}
    for item in proposed["items"]:
        features = eligibility(item)
        actual = disposition(features)
        counts[actual] = counts.get(actual, 0) + 1
        records.append(
            {
                "book": item["book"],
                "chunk_number": item["chunk_number"],
                "page_index": item["page_index"],
                "assembly_id": item["assembly_id"],
                "candidate_ids": item["candidate_ids"],
                "rendered_member": item["rendered_member"],
                "rendered_sha256": item["rendered_sha256"],
                "disposition": actual,
                "eligibility": features,
                "accepted": False,
                "review_required": True,
            }
        )
    body = {
        "contract_version": "1.0",
        "policy_version": "candidate-isolation-pilot-1",
        "source_inventory_id": proposed["inventory_id"],
        "source_inventory_sha256": digest(proposed_bytes),
        "record_count": len(records),
        "disposition_counts": dict(sorted(counts.items())),
        "records": records,
        "limitations": [
            "automated_unreviewed",
            "proposed_not_accepted",
            "pilot_policy_not_canonical",
        ],
    }
    value = {
        **body,
        "eligibility_inventory_id": identity(
            "reference-multimodal-equation-eligibility-inventory", body
        ),
    }
    content = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode()
        + b"\n"
    )
    path = ROOT / "equation-eligibility-pilot-1.json"
    if path.exists():
        if exact(path) != content:
            raise RuntimeError("create-once eligibility inventory differs")
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
                "eligibility_inventory_id": value["eligibility_inventory_id"],
                "eligibility_inventory_sha256": digest(content),
                "record_count": value["record_count"],
                "disposition_counts": value["disposition_counts"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
