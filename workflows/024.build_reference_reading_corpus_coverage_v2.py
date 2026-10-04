#!/Users/eugene/repos/projectkoios-ingestion/.venv/bin/python
from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from projectkoios.ingestion.page_projection import (
    PageProjectionPlanEntry,
    page_projection_validation_report_bytes,
    validate_page_projection,
)

ARTIFACTS = Path("/Users/eugene/projects/projectkoios/artifacts")
REFERENCES = Path("/Users/eugene/projects/projectkoios/references")
BASELINES = ARTIFACTS / "reference-page-resolution-v1" / "objects"
LEGACY = ARTIFACTS / "reference-multimodal-v1"
RECOMPOSED = ARTIFACTS / "reference-legacy-reading-transcripts-v3"
NEAMAN = ARTIFACTS / "reference-neaman-reading-transcript-v2"
PENDING = ARTIFACTS / "reference-reading-transcripts-v2"
OUTPUT = ARTIFACTS / "reference-reading-corpus-coverage-v2"


@dataclass(frozen=True)
class Book:
    document_id: str
    name: str
    filename: str
    title: str
    digest: str
    pages: int


BOOKS = (
    Book(
        "doc-01",
        "Kittel8ed",
        "Kittel8ed.pdf",
        "Introduction to Solid State Physics",
        "7c177d8ce281eeb1a1e0897e8d711bd908c2657ec42abd690ff1105533b7a6ed",
        700,
    ),
    Book(
        "doc-02",
        "SimonSS1Ed",
        "SimonSS1Ed.pdf",
        "The Oxford Solid State Basics",
        "46807198536b8672000463b8d9c8ae555f4955ba0ad0e80cec19b01671030be2",
        305,
    ),
    Book(
        "doc-03",
        "AshcroftMermin_SolidStatePhysics",
        "AshcroftMermin_SolidStatePhysics.pdf",
        "Solid State Physics",
        "6299153bde8e4ee49583ca8abfcc9afd687a34c25a0d06252681200fbda781ad",
        848,
    ),
    Book(
        "doc-04",
        "Marder2Ed",
        "Marder2Ed.pdf",
        "Condensed Matter Physics",
        "bc1ce37437da489aa1b35b5fe86750cf3bd35a9c0c9df7597b1e55871a243d93",
        985,
    ),
    Book(
        "doc-05",
        "SzeNg3Ed",
        "SzeNg3Ed.pdf",
        "Physics of Semiconductor Devices",
        "7909c81fe5c12006dbaf4f664b029b67319bd7c45fe86d97ccedaf229067a221",
        763,
    ),
    Book(
        "doc-06",
        "Neaman3Ed",
        "Neaman3Ed.pdf",
        "Semiconductor Physics and Devices",
        "31dce1ae5f09199951a496da12d00f7873f0ccbce00f3cd67449438b187d3761",
        566,
    ),
    Book(
        "doc-07",
        "SzeLee3Ed",
        "SzeLee3Ed.pdf",
        "Semiconductor Devices: Physics and Technology",
        "539257eb20229bee438dbd628e017bcf8ba6bb6348198ce1e9000cd685d7263e",
        590,
    ),
    Book(
        "doc-08",
        "YuCardona4Ed",
        "YuCardona4Ed.pdf",
        "Fundamentals of Semiconductors",
        "acfc317504ba1e20a14686c9cbf66b542fb844b4d29b9cc66307598961963f30",
        793,
    ),
    Book(
        "doc-09",
        "RudanPhysicsSemiconductors",
        "RudanPhysicsSemiconductors.pdf",
        "Physics of Semiconductor Devices",
        "53960e40556225a3b56cbd601409d737eb0f8384026550dce0bc16ef7aca7014",
        648,
    ),
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


def recognized_equation_text_count(transcript: bytes) -> tuple[int, int]:
    equation_count = 0
    recognized_count = 0
    for line in transcript.splitlines():
        page = json.loads(line)
        for block in page["blocks"]:
            if block.get("type") != "equation":
                continue
            equation_count += 1
            if (
                block.get("latex") is not None
                or block.get("mathml") is not None
            ):
                recognized_count += 1
    return equation_count, recognized_count


def main() -> None:
    records = []
    for book in BOOKS[:6]:
        root = (
            NEAMAN if book.document_id == "doc-06" else RECOMPOSED / book.name
        )
        transcript_path = root / "reading-transcript.jsonl"
        summary_path = root / "reading-transcript-summary.json"
        validation_path = root / "reading-transcript-validation.json"
        source_path = REFERENCES / book.digest / "document.pdf"
        baseline_path = (
            BASELINES
            / book.digest[:2]
            / book.digest
            / "composed-transcript.json"
        )
        projection = validate_page_projection(
            PageProjectionPlanEntry(
                document_id=book.document_id,
                filename=book.filename,
                title=book.title,
                source_sha256=book.digest,
                expected_page_count=book.pages,
            ),
            source_path=source_path,
            transcript_path=transcript_path,
            summary_path=summary_path,
            baseline_path=baseline_path,
            media_root=root,
        )
        retained_validation_bytes = exact(validation_path)
        expected_validation = page_projection_validation_report_bytes(
            projection.report
        )
        create_once(
            OUTPUT / "validations" / f"{book.document_id}.json",
            expected_validation,
        )
        transcript = exact(transcript_path)
        equation_count, recognized_count = recognized_equation_text_count(
            transcript
        )
        if equation_count != projection.report.equation_evidence_count:
            raise RuntimeError(f"{book.name}: equation count differs")
        if recognized_count:
            raise RuntimeError(f"{book.name}: recognized equation text remains")
        policy_status = "current_recognition_independent"
        records.append(
            {
                "document_id": book.document_id,
                "book": book.name,
                "source_sha256": book.digest,
                "page_count": book.pages,
                "artifact_root": str(root),
                "transcript_sha256": digest(transcript),
                "transcript_bytes": len(transcript),
                "summary_sha256": digest(exact(summary_path)),
                "validation_id": projection.report.validation_id,
                "validation_sha256": digest(expected_validation),
                "retained_validation_sha256": digest(retained_validation_bytes),
                "retained_validation_matches_current_baseline": retained_validation_bytes
                == expected_validation,
                "equation_evidence_count": equation_count,
                "figure_evidence_count": projection.report.figure_count,
                "recognized_equation_text_count": recognized_count,
                "policy_status": policy_status,
            }
        )

    pending_summary_bytes = exact(PENDING / "summary-all.json")
    pending_summary = json.loads(pending_summary_bytes)
    pending_validation_bytes = exact(PENDING / "validation.json")
    pending_validation = json.loads(pending_validation_bytes)
    if (
        pending_validation["status"] != "valid"
        or pending_validation["reading_transcript_collection_id"]
        != pending_summary["reading_transcript_collection_id"]
    ):
        raise RuntimeError("doc-07--doc-09 collection validation differs")
    by_name = {item["book"]: item for item in pending_summary["books"]}
    for book in BOOKS[6:]:
        member = by_name[book.name]
        root = PENDING / book.name
        transcript = exact(root / "reading-transcript.jsonl")
        summary_bytes = exact(root / "summary.json")
        summary = json.loads(summary_bytes)
        if (
            digest(transcript) != member["transcript_sha256"]
            or len(transcript) != member["transcript_utf8_bytes"]
        ):
            raise RuntimeError(f"{book.name}: collection transcript differs")
        recognized_count = 0
        equation_count = 0
        for line in transcript.splitlines():
            page = json.loads(line)
            for evidence in page["visual_evidence"]:
                if evidence["evidence_type"] == "equation":
                    equation_count += 1
                    if (
                        evidence["recognized_latex"] is not None
                        or evidence["recognized_mathml"] is not None
                    ):
                        recognized_count += 1
        if (
            equation_count != member["equation_evidence_count"]
            or recognized_count
        ):
            raise RuntimeError(
                f"{book.name}: equation evidence semantics differ"
            )
        records.append(
            {
                "document_id": book.document_id,
                "book": book.name,
                "source_sha256": book.digest,
                "page_count": book.pages,
                "artifact_root": str(root),
                "transcript_sha256": digest(transcript),
                "transcript_bytes": len(transcript),
                "summary_sha256": digest(summary_bytes),
                "validation_id": pending_validation["validation_id"],
                "validation_sha256": digest(pending_validation_bytes),
                "reading_transcript_id": summary["reading_transcript_id"],
                "equation_evidence_count": equation_count,
                "figure_evidence_count": member["figure_evidence_count"],
                "table_evidence_count": member["table_evidence_count"],
                "recognized_equation_text_count": 0,
                "policy_status": "current_recognition_independent",
            }
        )

    if [record["document_id"] for record in records] != [
        book.document_id for book in BOOKS
    ]:
        raise RuntimeError("document coverage differs")
    current_count = sum(
        record["policy_status"] == "current_recognition_independent"
        for record in records
    )
    legacy_count = len(records) - current_count
    if current_count != 9 or legacy_count != 0:
        raise RuntimeError("policy status coverage differs")
    stale_progress_bytes = exact(LEGACY / "progress.json")
    recomposed_summary_bytes = exact(RECOMPOSED / "summary-all.json")
    recomposed_summary = json.loads(recomposed_summary_bytes)
    neaman_resolution_bytes = exact(NEAMAN / "status-resolution.json")
    neaman_resolution = json.loads(neaman_resolution_bytes)
    body = {
        "contract_version": "1.0",
        "status": "complete",
        "document_count": len(records),
        "page_count": sum(record["page_count"] for record in records),
        "equation_evidence_count": sum(
            record["equation_evidence_count"] for record in records
        ),
        "figure_evidence_count": sum(
            record["figure_evidence_count"] for record in records
        ),
        "table_evidence_count": sum(
            record.get("table_evidence_count", 0) for record in records
        ),
        "current_policy_document_count": current_count,
        "legacy_recomposition_required_document_count": legacy_count,
        "recognized_equation_text_count": sum(
            record["recognized_equation_text_count"] for record in records
        ),
        "legacy_recomposed_collection_id": recomposed_summary["collection_id"],
        "legacy_recomposed_collection_sha256": digest(recomposed_summary_bytes),
        "legacy_mutable_progress_sha256": digest(stale_progress_bytes),
        "legacy_mutable_progress_status": json.loads(stale_progress_bytes)[
            "status"
        ],
        "neaman_status_resolution_id": neaman_resolution[
            "status_resolution_id"
        ],
        "neaman_status_resolution_sha256": digest(neaman_resolution_bytes),
        "pending_reading_collection_id": pending_summary[
            "reading_transcript_collection_id"
        ],
        "pending_reading_collection_summary_sha256": digest(
            pending_summary_bytes
        ),
        "documents": records,
        "model_execution_performed": False,
        "database_projection_performed": False,
        "search_indexing_performed": False,
        "publication_performed": False,
    }
    value = {
        **body,
        "coverage_inventory_id": identity(
            "reference-reading-corpus-coverage", body
        ),
    }
    content = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode()
        + b"\n"
    )
    status = create_once(OUTPUT / "coverage.json", content)
    print(
        json.dumps(
            {
                "status": status,
                "coverage_inventory_id": value["coverage_inventory_id"],
                "coverage_sha256": digest(content),
                "document_count": value["document_count"],
                "page_count": value["page_count"],
                "equation_evidence_count": value["equation_evidence_count"],
                "figure_evidence_count": value["figure_evidence_count"],
                "table_evidence_count": value["table_evidence_count"],
                "current_policy_document_count": current_count,
                "legacy_recomposition_required_document_count": legacy_count,
                "recognized_equation_text_count": value[
                    "recognized_equation_text_count"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    os.umask(0o077)
    main()
