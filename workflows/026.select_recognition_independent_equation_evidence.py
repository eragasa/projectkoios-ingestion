#!/Users/eugene/repos/projectkoios-ingestion/.venv/bin/python
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from collections import Counter
from pathlib import Path, PurePosixPath

DEFAULT_ROOT = Path(
    "/Users/eugene/projects/projectkoios/artifacts/reference-multimodal-preparation-v2"
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
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise RuntimeError(f"file is not private: {path}")
    return path.read_bytes()


def load_identified(
    path: Path, key: str, namespace: str
) -> tuple[dict[str, object], bytes]:
    content = exact(path)
    value = json.loads(content)
    if type(value) is not dict:
        raise RuntimeError(f"JSON object required: {path}")
    body = dict(value)
    observed = body.pop(key, None)
    if observed != identity(namespace, body):
        raise RuntimeError(f"identity differs: {path}")
    return value, content


def create_once(path: Path, content: bytes) -> str:
    if path.exists():
        if exact(path) != content:
            raise RuntimeError(f"create-once artifact differs: {path}")
        return "unchanged"
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    return "created"


def relative_member(value: object) -> PurePosixPath:
    if type(value) is not str:
        raise RuntimeError("evidence member path must be a string")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in ("", ".", "..") for part in path.parts)
    ):
        raise RuntimeError(f"unsafe evidence member path: {value}")
    return path


def validate_member(root: Path, member: dict[str, object]) -> None:
    relative = relative_member(member["path"])
    content = exact(root.joinpath(*relative.parts))
    if len(content) != member["bytes"] or digest(content) != member["sha256"]:
        raise RuntimeError(f"evidence member differs: {root / relative}")


def select(root: Path) -> dict[str, object]:
    plan, plan_bytes = load_identified(
        root / "plan.json",
        "plan_id",
        "reference-multimodal-preparation-plan",
    )
    summary, summary_bytes = load_identified(
        root / "quality-summary-all.json",
        "quality_summary_id",
        "reference-multimodal-quality-summary",
    )
    if summary["preparation_plan_id"] != plan["plan_id"]:
        raise RuntimeError(
            "quality summary does not match the preparation plan"
        )

    records: list[dict[str, object]] = []
    disposition_counts: Counter[str] = Counter()
    candidate_bytes: Counter[str] = Counter()
    candidate_member_counts: Counter[str] = Counter()
    book_counts: dict[str, Counter[str]] = {}
    quality_ids: list[str] = []
    assembly_ids: set[str] = set()
    candidate_ids: set[str] = set()
    selected_assembly_bytes = 0
    selected_assembly_member_count = 0

    for book in plan["books"]:
        book_name = book["book"]
        counts: Counter[str] = Counter()
        book_counts[book_name] = counts
        for chunk in book["chunks"]:
            number = int(chunk["chunk_number"])
            chunk_root = (
                root / "books" / book_name / "chunks" / f"chunk-{number:03d}"
            )
            quality, _ = load_identified(
                chunk_root / "quality-inventory.json",
                "quality_inventory_id",
                "reference-multimodal-quality-inventory",
            )
            inventory, _ = load_identified(
                chunk_root / "inventory.json",
                "inventory_id",
                "reference-multimodal-chunk-inventory",
            )
            if (
                quality["book"] != book_name
                or quality["chunk_number"] != number
                or quality["chunk_plan_id"] != chunk["chunk_plan_id"]
                or quality["evidence_inventory_id"] != inventory["inventory_id"]
            ):
                raise RuntimeError(
                    f"{book_name} chunk {number}: source binding differs"
                )
            quality_ids.append(quality["quality_inventory_id"])
            candidates = {
                item["candidate_id"]: item for item in quality["equations"]
            }
            if len(candidates) != len(quality["equations"]):
                raise RuntimeError(
                    f"{book_name} chunk {number}: duplicate equation candidate"
                )
            members = {item["path"]: item for item in inventory["members"]}
            if len(members) != len(inventory["members"]):
                raise RuntimeError(
                    f"{book_name} chunk {number}: duplicate evidence member"
                )
            primary_members = {
                item["assembly_id"]: item
                for item in quality["primary_recognition_members"]
            }
            if len(primary_members) != len(
                quality["primary_recognition_members"]
            ):
                raise RuntimeError(
                    f"{book_name} chunk {number}: duplicate assembly member"
                )

            for assembly in quality["equation_assemblies"]:
                assembly_id = assembly["assembly_id"]
                if assembly_id in assembly_ids:
                    raise RuntimeError(
                        f"equation assembly repeated: {assembly_id}"
                    )
                assembly_ids.add(assembly_id)
                reasons: list[str] = []
                if assembly["kind"] != "display":
                    reasons.append("assembly_kind_not_display")
                if assembly["rejected"]:
                    reasons.append("assembly_rejected")
                assembly_candidates = []
                evidence_members = []
                for candidate_id in assembly["candidate_ids"]:
                    candidate = candidates.get(candidate_id)
                    if candidate is None:
                        raise RuntimeError(
                            f"{book_name} chunk {number}: assembly candidate missing"
                        )
                    if candidate_id in candidate_ids:
                        raise RuntimeError(
                            f"equation candidate repeated: {candidate_id}"
                        )
                    candidate_ids.add(candidate_id)
                    assembly_candidates.append(candidate)
                    for path in candidate["rendered_members"]:
                        member = members.get(path)
                        if (
                            member is None
                            or member["candidate_id"] != candidate_id
                        ):
                            raise RuntimeError(
                                f"{book_name} chunk {number}: candidate member missing"
                            )
                        validate_member(chunk_root, member)
                        evidence_members.append(
                            {
                                "path": str(
                                    PurePosixPath("books")
                                    / book_name
                                    / "chunks"
                                    / f"chunk-{number:03d}"
                                    / relative_member(path)
                                ),
                                "sha256": member["sha256"],
                                "bytes": member["bytes"],
                            }
                        )
                if any(
                    item["evidence_status"] != "proposed"
                    for item in assembly_candidates
                ):
                    reasons.append("detector_evidence_not_proposed")
                if assembly["rejected"]:
                    disposition = "retained_rejected_equation_evidence"
                elif reasons:
                    disposition = "retained_auxiliary_equation_evidence"
                else:
                    disposition = "selected_primary_equation_evidence"
                expected_quality_disposition = {
                    "selected_primary_equation_evidence": "proposed_primary_recognition",
                    "retained_auxiliary_equation_evidence": "retained_non_primary",
                    "retained_rejected_equation_evidence": "deferred_prefilter_rejected",
                }[disposition]
                if assembly["disposition"] != expected_quality_disposition:
                    raise RuntimeError(
                        f"{book_name} chunk {number}: source disposition differs"
                    )

                assembly_member = primary_members.get(assembly_id)
                rendered_member = None
                if disposition == "selected_primary_equation_evidence":
                    if (
                        assembly_member is None
                        or assembly["rendered_member"]
                        != assembly_member["path"]
                    ):
                        raise RuntimeError(
                            f"{book_name} chunk {number}: selected assembly image missing"
                        )
                    validate_member(chunk_root, assembly_member)
                    rendered_member = {
                        "path": str(
                            PurePosixPath("books")
                            / book_name
                            / "chunks"
                            / f"chunk-{number:03d}"
                            / relative_member(assembly_member["path"])
                        ),
                        "sha256": assembly_member["sha256"],
                        "bytes": assembly_member["bytes"],
                    }
                    selected_assembly_bytes += int(assembly_member["bytes"])
                    selected_assembly_member_count += 1
                elif (
                    assembly_member is not None
                    or assembly["rendered_member"] is not None
                ):
                    raise RuntimeError(
                        f"{book_name} chunk {number}: non-primary assembly image promoted"
                    )

                record = {
                    "book": book_name,
                    "chunk_number": number,
                    "page_index": assembly["page_index"],
                    "assembly_id": assembly_id,
                    "candidate_ids": assembly["candidate_ids"],
                    "source_quality_inventory_id": quality[
                        "quality_inventory_id"
                    ],
                    "disposition": disposition,
                    "ineligibility_reasons": reasons,
                    "candidate_evidence_members": evidence_members,
                    "assembly_rendered_member": rendered_member,
                    "review_status": "unreviewed",
                    "accepted": False,
                    "review_required": True,
                    "chunk_text_eligible": False,
                    "recognized_text_retained": False,
                }
                records.append(record)
                disposition_counts[disposition] += 1
                counts[disposition] += 1
                member_bytes = sum(
                    int(item["bytes"]) for item in evidence_members
                )
                candidate_bytes[disposition] += member_bytes
                candidate_member_counts[disposition] += len(evidence_members)

    if len(records) != summary["equation_assembly_count"]:
        raise RuntimeError("equation assembly coverage differs")
    if len(candidate_ids) != summary["equation_candidate_count"]:
        raise RuntimeError("equation candidate coverage differs")
    if (
        len(quality_ids) != summary["chunk_count"]
        or quality_ids != summary["quality_inventory_ids"]
    ):
        raise RuntimeError("quality inventory coverage differs")
    if (
        disposition_counts["selected_primary_equation_evidence"]
        != summary["proposed_primary_recognition_count"]
    ):
        raise RuntimeError("selected equation evidence count differs")
    if (
        disposition_counts["retained_auxiliary_equation_evidence"]
        != summary["retained_non_primary_count"]
    ):
        raise RuntimeError("auxiliary equation evidence count differs")
    if (
        disposition_counts["retained_rejected_equation_evidence"]
        != summary["deferred_prefilter_rejected_count"]
    ):
        raise RuntimeError("rejected equation evidence count differs")
    if selected_assembly_bytes != summary["primary_member_bytes"]:
        raise RuntimeError("selected assembly image bytes differ")

    body = {
        "contract_version": "1.0",
        "policy_version": "recognition-independent-equation-evidence-selection-1",
        "preparation_plan_id": plan["plan_id"],
        "preparation_plan_sha256": digest(plan_bytes),
        "quality_summary_id": summary["quality_summary_id"],
        "quality_summary_sha256": digest(summary_bytes),
        "book_count": len(book_counts),
        "chunk_count": len(quality_ids),
        "assembly_count": len(records),
        "candidate_count": len(candidate_ids),
        "disposition_counts": dict(sorted(disposition_counts.items())),
        "candidate_evidence_member_counts_by_disposition": dict(
            sorted(candidate_member_counts.items())
        ),
        "candidate_evidence_bytes_by_disposition": dict(
            sorted(candidate_bytes.items())
        ),
        "selected_assembly_member_count": selected_assembly_member_count,
        "selected_assembly_bytes": selected_assembly_bytes,
        "book_disposition_counts": {
            book: dict(sorted(counts.items()))
            for book, counts in sorted(book_counts.items())
        },
        "quality_inventory_ids": quality_ids,
        "records": records,
        "recognized_text_retained_count": 0,
        "accepted_count": 0,
        "review_required_count": len(records),
        "chunk_text_eligible_count": 0,
        "model_execution_performed": False,
    }
    return {
        **body,
        "selection_inventory_id": identity(
            "reference-equation-evidence-selection-inventory", body
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Select equation evidence without recognition output."
    )
    parser.add_argument("--preparation-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    root = arguments.preparation_root.resolve()
    output = arguments.output or root / "equation-evidence-selection-v1.json"
    value = select(root)
    content = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode()
        + b"\n"
    )
    status = create_once(output, content)
    print(
        json.dumps(
            {
                "status": status,
                "output": str(output),
                "selection_inventory_id": value["selection_inventory_id"],
                "selection_inventory_sha256": digest(content),
                "assembly_count": value["assembly_count"],
                "candidate_count": value["candidate_count"],
                "disposition_counts": value["disposition_counts"],
                "recognized_text_retained_count": 0,
                "model_execution_performed": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    os.umask(0o077)
    main()
