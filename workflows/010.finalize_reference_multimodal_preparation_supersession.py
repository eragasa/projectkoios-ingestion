#!/Users/eugene/repos/projectkoios-ingestion/.venv/bin/python
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pymupdf

ARTIFACTS = Path("/Users/eugene/projects/projectkoios/artifacts")
V1 = ARTIFACTS / "reference-multimodal-preparation-v1"
V2 = ARTIFACTS / "reference-multimodal-preparation-v2"
REFERENCES = Path("/Users/eugene/projects/projectkoios/references")


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


def create_once(path: Path, value: object) -> str:
    content = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode()
        + b"\n"
    )
    if path.exists():
        if exact(path) != content:
            raise RuntimeError(f"create-once artifact differs: {path}")
        return "unchanged"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    return "created"


def derived(source: bytes, first: int, last: int) -> bytes:
    original = pymupdf.open(stream=source, filetype="pdf")
    result = pymupdf.open()
    try:
        result.insert_pdf(original, from_page=first, to_page=last - 1)
        return result.tobytes(garbage=4, deflate=True, no_new_id=True)
    finally:
        result.close()
        original.close()


def main() -> None:
    plan = json.loads(exact(V2 / "plan.json"))
    quality = json.loads(exact(V2 / "quality-summary-all.json"))
    validation = json.loads(exact(V2 / "validation.json"))
    replayed = []
    for book in plan["books"]:
        source = exact(REFERENCES / book["source_sha256"] / "document.pdf")
        if digest(source) != book["source_sha256"]:
            raise RuntimeError(f"source changed: {book['book']}")
        for chunk in book["chunks"]:
            inventory_path = (
                V2
                / "books"
                / book["book"]
                / "chunks"
                / f"chunk-{chunk['chunk_number']:03d}"
                / "inventory.json"
            )
            inventory = json.loads(exact(inventory_path))
            content = derived(
                source,
                chunk["first_page_index"],
                chunk["last_page_index_exclusive"],
            )
            if (
                len(content) != inventory["chunk_pdf_bytes"]
                or digest(content) != inventory["chunk_pdf_sha256"]
            ):
                raise RuntimeError(
                    f"derived-source replay differs: {book['book']} {chunk['chunk_number']}"
                )
            replayed.append(inventory["inventory_id"])
    body = {
        "contract_version": "1.0",
        "status": "valid",
        "plan_id": plan["plan_id"],
        "validation_id": validation["validation_id"],
        "quality_summary_id": quality["quality_summary_id"],
        "chunk_count": len(replayed),
        "chunk_inventory_ids": replayed,
        "derived_source_recomputation": "all_sha256_and_byte_lengths_match",
        "detection_recomputation": "all_detection_result_ids_matched_during_quality_inventory_creation",
    }
    replay = {
        **body,
        "replay_validation_id": identity(
            "reference-multimodal-replay-validation", body
        ),
    }
    replay_status = create_once(V2 / "replay-validation.json", replay)
    supersession_body = {
        "contract_version": "1.0",
        "status": "superseded",
        "superseded_artifact_root": str(V1),
        "authoritative_artifact_root": str(V2),
        "reason": "v1 derived chunk PDFs used backend-generated document IDs and were not retained, so fresh derivation changed chunk hashes and detection identities",
        "retention": "v1 retained for audit only and must not be used as deterministic preparation authority",
        "authoritative_plan_id": plan["plan_id"],
        "authoritative_validation_id": validation["validation_id"],
        "authoritative_replay_validation_id": replay["replay_validation_id"],
    }
    supersession = {
        **supersession_body,
        "supersession_id": identity(
            "reference-multimodal-preparation-supersession", supersession_body
        ),
    }
    supersession_status = create_once(V1 / "SUPERSEDED.json", supersession)
    link_status = create_once(V2 / "supersedes-v1.json", supersession)
    print(
        json.dumps(
            {
                "replay_status": replay_status,
                "replay_validation_id": replay["replay_validation_id"],
                "replay_validation_sha256": digest(
                    exact(V2 / "replay-validation.json")
                ),
                "supersession_status": supersession_status,
                "supersession_link_status": link_status,
                "supersession_id": supersession["supersession_id"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
