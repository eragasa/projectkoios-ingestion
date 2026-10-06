#!/Users/eugene/repos/projectkoios-ingestion/.venv/bin/python
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter

ROOT = Path(
    "/Users/eugene/projects/projectkoios/artifacts/reference-multimodal-preparation-v2"
)


def digest(content: bytes) -> str:
    return SHA256Fingerprinter.fingerprint(content=content)


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()


def exact(path: Path) -> bytes:
    if (
        path.is_symlink()
        or not path.is_file()
        or stat.S_IMODE(path.stat().st_mode) != 0o600
    ):
        raise RuntimeError(f"unsafe artifact: {path}")
    return path.read_bytes()


def main() -> None:
    for directory in ROOT.rglob("*"):
        if (
            directory.is_dir()
            and stat.S_IMODE(directory.stat().st_mode) != 0o700
        ):
            raise RuntimeError(f"unsafe directory permissions: {directory}")
    plan_bytes = exact(ROOT / "plan.json")
    summary_bytes = exact(ROOT / "summary-all.json")
    plan = json.loads(plan_bytes)
    summary = json.loads(summary_bytes)
    inventories = tuple(
        sorted(ROOT.glob("books/*/chunks/chunk-*/inventory.json"))
    )
    if len(inventories) != summary["chunk_count"] != 204:
        raise RuntimeError("chunk inventory coverage differs")
    observed_ids = []
    observed_members = 0
    observed_bytes = 0
    derived_source_bytes = 0
    for inventory_path in inventories:
        inventory = json.loads(exact(inventory_path))
        source_content = exact(
            inventory_path.parent / inventory["derived_source_path"]
        )
        if (
            len(source_content) != inventory["chunk_pdf_bytes"]
            or digest(source_content) != inventory["chunk_pdf_sha256"]
        ):
            raise RuntimeError(
                f"derived source differs: {inventory_path.parent}"
            )
        derived_source_bytes += len(source_content)
        observed_ids.append(inventory["inventory_id"])
        for member in inventory["members"]:
            content = exact(inventory_path.parent / member["path"])
            if (
                len(content) != member["bytes"]
                or digest(content) != member["sha256"]
            ):
                raise RuntimeError(
                    f"member differs: {inventory_path.parent / member['path']}"
                )
            observed_members += 1
            observed_bytes += len(content)
    expected_ids = summary["chunk_inventory_ids"]
    if len(set(observed_ids)) != len(observed_ids) or set(observed_ids) != set(
        expected_ids
    ):
        raise RuntimeError("chunk inventory identities differ")
    if (
        observed_members != summary["member_count"]
        or observed_bytes != summary["member_bytes"]
    ):
        raise RuntimeError("aggregate member inventory differs")
    quality_bytes = exact(ROOT / "quality-summary-all.json")
    quality = json.loads(quality_bytes)
    execution_bytes = exact(ROOT / "equation-execution-plan.json")
    execution = json.loads(execution_bytes)
    quality_paths = tuple(
        sorted(ROOT.glob("books/*/chunks/chunk-*/quality-inventory.json"))
    )
    if len(quality_paths) != len(inventories):
        raise RuntimeError("quality inventory coverage differs")
    quality_ids = {
        json.loads(exact(path))["quality_inventory_id"]
        for path in quality_paths
    }
    if quality_ids != set(quality["quality_inventory_ids"]):
        raise RuntimeError("quality inventory identities differ")
    for inventory_name, expected_id in execution["inventory_ids"].items():
        inventory = json.loads(exact(ROOT / f"{inventory_name}-inventory.json"))
        if inventory["inventory_id"] != expected_id:
            raise RuntimeError(
                f"execution inventory identity differs: {inventory_name}"
            )
    body = {
        "contract_version": "2.0",
        "status": "valid",
        "plan_id": plan["plan_id"],
        "plan_sha256": digest(plan_bytes),
        "summary_id": summary["summary_id"],
        "summary_sha256": digest(summary_bytes),
        "quality_summary_id": quality["quality_summary_id"],
        "quality_summary_sha256": digest(quality_bytes),
        "equation_execution_plan_id": execution["execution_plan_id"],
        "equation_execution_plan_sha256": digest(execution_bytes),
        "book_count": len(plan["books"]),
        "page_count": sum(book["page_count"] for book in plan["books"]),
        "chunk_count": len(inventories),
        "member_count": observed_members,
        "member_bytes": observed_bytes,
        "derived_source_bytes": derived_source_bytes,
        "equation_candidate_count": summary["equation_candidate_count"],
        "figure_candidate_count": summary["figure_candidate_count"],
        "table_candidate_count": summary["table_candidate_count"],
        "equation_assembly_count": quality["equation_assembly_count"],
        "proposed_primary_recognition_count": quality[
            "proposed_primary_recognition_count"
        ],
        "retained_non_primary_count": quality["retained_non_primary_count"],
        "deferred_prefilter_rejected_count": quality[
            "deferred_prefilter_rejected_count"
        ],
        "primary_member_bytes": quality["primary_member_bytes"],
        "ocr_artifact_count": sum(
            book["ocr_artifact_count"] for book in plan["books"]
        ),
        "limitations": [
            "automated_unreviewed_candidates",
            "candidate_evidence_not_accepted",
            "no_model_execution",
            "no_search_or_indexing",
            "no_publication",
        ],
    }
    value = {
        **body,
        "validation_id": f"reference-multimodal-preparation-validation:sha256:{digest(canonical(body))}",
    }
    content = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode()
        + b"\n"
    )
    path = ROOT / "validation.json"
    if path.exists():
        if exact(path) != content:
            raise RuntimeError("create-once validation differs")
        status = "unchanged"
    else:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        status = "created"
    print(json.dumps({"status": status, **value}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
