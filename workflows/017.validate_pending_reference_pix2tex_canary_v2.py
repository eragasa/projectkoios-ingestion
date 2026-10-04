#!/Users/eugene/repos/projectkoios-ingestion/.venv/bin/python
from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

ROOT = Path(
    "/Users/eugene/projects/projectkoios/artifacts/reference-multimodal-preparation-v2/pix2tex-canary-v2"
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
    if (
        path.is_symlink()
        or not path.is_file()
        or stat.S_IMODE(path.stat().st_mode) != 0o600
    ):
        raise RuntimeError(f"unsafe artifact: {path}")
    return path.read_bytes()


def main() -> None:
    for directory in (ROOT, ROOT / "results"):
        if (
            directory.is_symlink()
            or not directory.is_dir()
            or stat.S_IMODE(directory.stat().st_mode) != 0o700
        ):
            raise RuntimeError(f"unsafe directory: {directory}")
    plan_bytes = exact(ROOT / "plan.json")
    inventory_bytes = exact(ROOT / "inventory.json")
    audit_bytes = exact(ROOT / "automated-visual-audit.json")
    plan = json.loads(plan_bytes)
    inventory = json.loads(inventory_bytes)
    audit = json.loads(audit_bytes)
    if (
        plan["item_count"] != 30
        or inventory["result_count"] != 30
        or audit["record_count"] != 30
    ):
        raise RuntimeError("canary coverage differs")
    if (
        inventory["canary_plan_id"] != plan["canary_plan_id"]
        or audit["canary_inventory_id"] != inventory["canary_inventory_id"]
    ):
        raise RuntimeError("canary identity chain differs")
    records = []
    for item, record in zip(plan["items"], inventory["records"], strict=True):
        path = ROOT / record["path"]
        content = exact(path)
        if (
            len(content) != record["bytes"]
            or digest(content) != record["sha256"]
        ):
            raise RuntimeError(f"result member differs: {path}")
        value = json.loads(content)
        if (
            value["assembly_id"] != item["assembly_id"]
            or value["request_id"] != record["request_id"]
        ):
            raise RuntimeError(f"result binding differs: {path}")
        if (
            value["accepted"] is not False
            or value["reviewed"] is not False
            or value["chunk_text_eligible"] is not False
        ):
            raise RuntimeError(f"result semantics differ: {path}")
        records.append(record["sha256"])
    body = {
        "contract_version": "1.0",
        "status": "valid",
        "canary_plan_id": plan["canary_plan_id"],
        "canary_plan_sha256": digest(plan_bytes),
        "canary_inventory_id": inventory["canary_inventory_id"],
        "canary_inventory_sha256": digest(inventory_bytes),
        "automated_visual_audit_id": audit["audit_id"],
        "automated_visual_audit_sha256": digest(audit_bytes),
        "result_count": len(records),
        "result_sha256s": records,
        "proposed_count": inventory["proposed_count"],
        "failed_count": inventory["failed_count"],
        "nonzero_exit_count": inventory["nonzero_exit_count"],
        "accepted_count": audit["accepted_count"],
        "human_review_required_count": audit["human_review_required_count"],
        "replay_behavior": "existing exact result journal reused without model invocation",
    }
    value = {
        **body,
        "validation_id": identity(
            "reference-multimodal-pix2tex-canary-validation", body
        ),
    }
    content = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode()
        + b"\n"
    )
    path = ROOT / "validation.json"
    if path.exists():
        if exact(path) != content:
            raise RuntimeError("create-once canary validation differs")
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
                "validation_id": value["validation_id"],
                "validation_sha256": digest(content),
                "result_count": value["result_count"],
                "proposed_count": value["proposed_count"],
                "failed_count": value["failed_count"],
                "nonzero_exit_count": value["nonzero_exit_count"],
                "accepted_count": value["accepted_count"],
                "human_review_required_count": value[
                    "human_review_required_count"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
