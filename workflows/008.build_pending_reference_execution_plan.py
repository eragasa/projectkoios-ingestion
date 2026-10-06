#!/Users/eugene/repos/projectkoios-ingestion/.venv/bin/python
from __future__ import annotations

import json
import os
from pathlib import Path

from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter

ROOT = Path(
    "/Users/eugene/projects/projectkoios/artifacts/reference-multimodal-preparation-v2"
)
BATCH_SIZE = 100


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


def publish(name: str, body: dict[str, object]) -> tuple[str, str, str]:
    value = {
        **body,
        "inventory_id": identity(
            f"reference-multimodal-{name}-inventory", body
        ),
    }
    content = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode()
        + b"\n"
    )
    path = ROOT / f"{name}-inventory.json"
    if path.exists():
        if exact(path) != content:
            raise RuntimeError(f"create-once inventory differs: {path}")
        status = "unchanged"
    else:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        status = "created"
    return status, value["inventory_id"], digest(content)


def main() -> None:
    quality_paths = tuple(
        sorted(ROOT.glob("books/*/chunks/chunk-*/quality-inventory.json"))
    )
    proposed = []
    retained = []
    deferred = []
    for path in quality_paths:
        value = json.loads(exact(path))
        equation_members = {
            item["candidate_id"]: item["rendered_members"]
            for item in value["equations"]
        }
        primary_members = {
            item["assembly_id"]: item
            for item in value["primary_recognition_members"]
        }
        for assembly in value["equation_assemblies"]:
            base = {
                "book": value["book"],
                "chunk_number": value["chunk_number"],
                "quality_inventory_id": value["quality_inventory_id"],
                "assembly_id": assembly["assembly_id"],
                "candidate_ids": assembly["candidate_ids"],
                "kind": assembly["kind"],
                "page_index": assembly["page_index"],
                "source_spans": assembly["source_spans"],
                "raw_fragments": assembly["raw_fragments"],
                "sanitized_native_text": assembly["sanitized_native_text"],
                "prefilter_reasons": assembly["prefilter_reasons"],
                "evidence_members": [
                    member
                    for candidate_id in assembly["candidate_ids"]
                    for member in equation_members[candidate_id]
                ],
            }
            disposition = assembly["disposition"]
            if disposition == "proposed_primary_recognition":
                member = primary_members[assembly["assembly_id"]]
                member_path = path.parent / member["path"]
                payload = exact(member_path)
                if (
                    len(payload) != member["bytes"]
                    or digest(payload) != member["sha256"]
                ):
                    raise RuntimeError(f"primary member differs: {member_path}")
                proposed.append(
                    {
                        **base,
                        "rendered_member": str(member_path.relative_to(ROOT)),
                        "rendered_sha256": member["sha256"],
                        "rendered_bytes": member["bytes"],
                        "status": "proposed_unreviewed_unaccepted",
                    }
                )
            elif disposition == "retained_non_primary":
                retained.append({**base, "status": "retained_not_proposed"})
            elif disposition == "deferred_prefilter_rejected":
                deferred.append({**base, "status": "deferred_not_discarded"})
            else:
                raise RuntimeError(f"unsupported disposition: {disposition}")
    for sequence, item in enumerate(proposed, 1):
        item["sequence"] = sequence
        item["batch_number"] = ((sequence - 1) // BATCH_SIZE) + 1
    common = {
        "contract_version": "1.0",
        "quality_summary_id": json.loads(
            exact(ROOT / "quality-summary-all.json")
        )["quality_summary_id"],
        "automated": True,
        "reviewed": False,
        "accepted": False,
        "model_executed": False,
    }
    outputs = {}
    for name, items in (
        ("proposed-primary-recognition", proposed),
        ("retained-non-primary", retained),
        ("deferred-prefilter-rejected", deferred),
    ):
        body = {**common, "count": len(items), "items": items}
        outputs[name] = publish(name, body)
    plan_body = {
        **common,
        "batch_size": BATCH_SIZE,
        "batch_count": (len(proposed) + BATCH_SIZE - 1) // BATCH_SIZE,
        "proposed_primary_recognition_count": len(proposed),
        "retained_non_primary_count": len(retained),
        "deferred_prefilter_rejected_count": len(deferred),
        "inventory_ids": {name: result[1] for name, result in outputs.items()},
        "authorization_state": "planned_not_authorized_for_model_execution",
    }
    plan = {
        **plan_body,
        "execution_plan_id": identity(
            "reference-multimodal-equation-execution-plan", plan_body
        ),
    }
    content = (
        json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True).encode()
        + b"\n"
    )
    path = ROOT / "equation-execution-plan.json"
    if path.exists():
        if exact(path) != content:
            raise RuntimeError("create-once execution plan differs")
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
                "execution_plan_id": plan["execution_plan_id"],
                "execution_plan_sha256": digest(content),
                "batch_count": plan["batch_count"],
                "proposed_primary_recognition_count": len(proposed),
                "retained_non_primary_count": len(retained),
                "deferred_prefilter_rejected_count": len(deferred),
                "inventory_results": {
                    name: {
                        "status": result[0],
                        "inventory_id": result[1],
                        "sha256": result[2],
                    }
                    for name, result in outputs.items()
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
