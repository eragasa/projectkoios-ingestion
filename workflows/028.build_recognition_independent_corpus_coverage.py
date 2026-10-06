#!/Users/eugene/repos/projectkoios-ingestion/.venv/bin/python
from __future__ import annotations

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
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter

ARTIFACTS = Path("/Users/eugene/projects/projectkoios/artifacts")
REFERENCES = Path("/Users/eugene/projects/projectkoios/references")
BASELINES = ARTIFACTS / "reference-page-resolution-v1" / "objects"
LEGACY = ARTIFACTS / "reference-multimodal-v1"
RECOMPOSED = ARTIFACTS / "reference-legacy-reading-transcripts-v3"
NEAMAN = ARTIFACTS / "reference-neaman-reading-transcript-v2"
PENDING = ARTIFACTS / "reference-reading-transcripts-v3"
OUTPUT = ARTIFACTS / "reference-reading-corpus-coverage-v3"
PREPARATION = ARTIFACTS / "reference-multimodal-preparation-v2"
PREVIOUS_PENDING = ARTIFACTS / "reference-reading-transcripts-v2"
PREVIOUS_COVERAGE = ARTIFACTS / "reference-reading-corpus-coverage-v2"
PNG = b"\x89PNG\r\n\x1a\n"


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
    return SHA256Fingerprinter.fingerprint(content=content)


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


def validate_media(root: Path, value: dict[str, object]) -> str:
    relative = value["png_path"]
    path = root / relative
    content = exact(path)
    if not content.startswith(PNG):
        raise RuntimeError(f"media is not PNG: {path}")
    expected = value.get("png_sha256")
    if expected is not None and digest(content) != expected:
        raise RuntimeError(f"media digest differs: {path}")
    return str(path)


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
    pending_summary_body = dict(pending_summary)
    pending_collection_id = pending_summary_body.pop(
        "reading_transcript_collection_id"
    )
    if pending_collection_id != identity(
        "reference-reading-transcript-collection", pending_summary_body
    ):
        raise RuntimeError("doc-07--doc-09 collection identity differs")
    pending_validation_bytes = exact(PENDING / "validation.json")
    pending_validation = json.loads(pending_validation_bytes)
    if (
        pending_validation["status"] != "valid"
        or pending_validation["reading_transcript_collection_id"]
        != pending_summary["reading_transcript_collection_id"]
        or pending_validation["equation_evidence_selection_inventory_id"]
        != pending_summary["equation_evidence_selection_inventory_id"]
        or pending_validation["semantic_equivalence_status"] != "equivalent"
    ):
        raise RuntimeError("doc-07--doc-09 collection validation differs")
    by_name = {item["book"]: item for item in pending_summary["books"]}
    for book in BOOKS[6:]:
        member = by_name[book.name]
        root = PENDING / book.name
        transcript = exact(root / "reading-transcript.jsonl")
        summary_bytes = exact(root / "summary.json")
        summary = json.loads(summary_bytes)
        summary_body = dict(summary)
        transcript_id = summary_body.pop("reading_transcript_id")
        if (
            transcript_id
            != identity("reference-reading-transcript", summary_body)
            or transcript_id != member["reading_transcript_id"]
            or digest(transcript) != member["transcript_sha256"]
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
                        evidence["selection_disposition"]
                        != "selected_primary_equation_evidence"
                        or evidence["selection_inventory_id"]
                        != pending_summary[
                            "equation_evidence_selection_inventory_id"
                        ]
                        or evidence["recognition_status"] != "not_requested"
                        or evidence["review_status"] != "unreviewed"
                        or evidence["accepted"] is not False
                        or evidence["review_required"] is not True
                        or evidence["chunk_text_eligible"] is not False
                    ):
                        raise RuntimeError(
                            f"{book.name}: equation selection semantics differ"
                        )
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
        "recognition_independent_reading_collection_id": pending_summary[
            "reading_transcript_collection_id"
        ],
        "recognition_independent_reading_collection_summary_sha256": digest(
            pending_summary_bytes
        ),
        "equation_evidence_selection_inventory_id": pending_summary[
            "equation_evidence_selection_inventory_id"
        ],
        "equation_evidence_selection_inventory_sha256": pending_summary[
            "equation_evidence_selection_inventory_sha256"
        ],
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

    previous_coverage_bytes = exact(PREVIOUS_COVERAGE / "coverage.json")
    previous_coverage = json.loads(previous_coverage_bytes)
    previous_body = dict(previous_coverage)
    previous_coverage_id = previous_body.pop("coverage_inventory_id")
    if previous_coverage_id != identity(
        "reference-reading-corpus-coverage", previous_body
    ):
        raise RuntimeError("previous coverage identity differs")
    previous_by_document = {
        item["document_id"]: item for item in previous_coverage["documents"]
    }
    semantic_document_keys = (
        "document_id",
        "book",
        "source_sha256",
        "page_count",
        "equation_evidence_count",
        "figure_evidence_count",
        "recognized_equation_text_count",
    )
    for record in records:
        previous = previous_by_document.get(record["document_id"])
        if previous is None or any(
            record[key] != previous[key] for key in semantic_document_keys
        ):
            raise RuntimeError(
                f"{record['document_id']}: previous coverage semantics differ"
            )
        if record.get("table_evidence_count", 0) != previous.get(
            "table_evidence_count", 0
        ):
            raise RuntimeError(
                f"{record['document_id']}: previous table coverage differs"
            )

    selection_bytes = exact(PREPARATION / "equation-evidence-selection-v1.json")
    selection = json.loads(selection_bytes)
    selection_body = dict(selection)
    selected_inventory_id = selection_body.pop("selection_inventory_id")
    if (
        selected_inventory_id
        != identity(
            "reference-equation-evidence-selection-inventory", selection_body
        )
        or selected_inventory_id
        != value["equation_evidence_selection_inventory_id"]
        or digest(selection_bytes)
        != value["equation_evidence_selection_inventory_sha256"]
    ):
        raise RuntimeError("equation evidence selection binding differs")
    selected_pending_ids = {
        item["assembly_id"]
        for item in selection["records"]
        if item["disposition"] == "selected_primary_equation_evidence"
    }
    auxiliary_pending_ids = {
        item["assembly_id"]
        for item in selection["records"]
        if item["disposition"] == "retained_auxiliary_equation_evidence"
    }

    equation_ids: set[str] = set()
    pending_equation_ids: set[str] = set()
    media_paths: set[str] = set()
    page_count = 0
    equation_count = 0
    figure_count = 0
    table_count = 0
    for record in records:
        root = Path(record["artifact_root"])
        transcript = exact(root / "reading-transcript.jsonl")
        lines = transcript.splitlines()
        if len(lines) != record["page_count"]:
            raise RuntimeError(f"{record['book']}: page coverage differs")
        document_equations = 0
        document_figures: set[str] = set()
        document_tables: set[str] = set()
        for page_index, line in enumerate(lines):
            page = json.loads(line)
            if record["document_id"] <= "doc-06":
                if page["physical_page"] != page_index + 1:
                    raise RuntimeError(f"{record['book']}: page order differs")
                for block in page["blocks"]:
                    kind = block["type"]
                    if kind == "equation":
                        equation_id = block["assembly_id"]
                        if equation_id in equation_ids:
                            raise RuntimeError(
                                "equation identity is duplicated"
                            )
                        if (
                            block["latex"] is not None
                            or block["mathml"] is not None
                            or block["review_status"] != "unreviewed"
                            or block["accepted"] is not False
                            or block["review_required"] is not True
                            or block["chunk_text_eligible"] is not False
                        ):
                            raise RuntimeError("equation review gate differs")
                        equation_ids.add(equation_id)
                        document_equations += 1
                        media_paths.add(validate_media(root, block))
                    elif kind == "figure":
                        document_figures.add(
                            block.get("candidate_id", block["png_path"])
                        )
                        media_paths.add(validate_media(root, block))
            else:
                if (
                    page["page_index"] != page_index
                    or page["physical_page"] != page_index + 1
                ):
                    raise RuntimeError(f"{record['book']}: page order differs")
                for evidence in page["visual_evidence"]:
                    kind = evidence["evidence_type"]
                    if kind == "equation":
                        equation_id = evidence["assembly_id"]
                        if (
                            equation_id in equation_ids
                            or equation_id not in selected_pending_ids
                            or equation_id in auxiliary_pending_ids
                        ):
                            raise RuntimeError(
                                "selected equation projection differs"
                            )
                        if (
                            evidence["recognized_latex"] is not None
                            or evidence["recognized_mathml"] is not None
                            or evidence["selection_disposition"]
                            != "selected_primary_equation_evidence"
                            or evidence["selection_inventory_id"]
                            != selected_inventory_id
                            or evidence["recognition_status"] != "not_requested"
                            or evidence["review_status"] != "unreviewed"
                            or evidence["accepted"] is not False
                            or evidence["review_required"] is not True
                            or evidence["chunk_text_eligible"] is not False
                        ):
                            raise RuntimeError("equation review gate differs")
                        equation_ids.add(equation_id)
                        pending_equation_ids.add(equation_id)
                        document_equations += 1
                    elif kind == "figure":
                        document_figures.add(evidence["candidate_id"])
                    elif kind == "table":
                        document_tables.add(evidence["candidate_id"])
                    for rendered in evidence["rendered_members"]:
                        path = PREPARATION / rendered["path"]
                        payload = exact(path)
                        if (
                            len(payload) != rendered["bytes"]
                            or digest(payload) != rendered["sha256"]
                        ):
                            raise RuntimeError(
                                f"rendered evidence differs: {path}"
                            )
                        media_paths.add(str(path))
        if (
            document_equations != record["equation_evidence_count"]
            or len(document_figures) != record["figure_evidence_count"]
            or len(document_tables) != record.get("table_evidence_count", 0)
        ):
            raise RuntimeError(f"{record['book']}: evidence counts differ")
        page_count += len(lines)
        equation_count += document_equations
        figure_count += len(document_figures)
        table_count += len(document_tables)
    if pending_equation_ids != selected_pending_ids:
        raise RuntimeError("selected equation inventory is not projected once")
    if (
        page_count != value["page_count"]
        or equation_count != value["equation_evidence_count"]
        or figure_count != value["figure_evidence_count"]
        or table_count != value["table_evidence_count"]
        or len(equation_ids) != equation_count
    ):
        raise RuntimeError("corpus coverage totals differ")

    validation_body = {
        "contract_version": "1.0",
        "status": "valid",
        "coverage_inventory_id": value["coverage_inventory_id"],
        "coverage_sha256": digest(content),
        "semantic_authority_coverage_inventory_id": previous_coverage_id,
        "semantic_authority_coverage_sha256": digest(previous_coverage_bytes),
        "semantic_equivalence_status": "equivalent",
        "equation_evidence_selection_inventory_id": selected_inventory_id,
        "equation_evidence_selection_inventory_sha256": digest(selection_bytes),
        "document_count": value["document_count"],
        "page_count": page_count,
        "equation_evidence_count": equation_count,
        "figure_evidence_count": figure_count,
        "table_evidence_count": table_count,
        "recognized_equation_text_count": 0,
        "accepted_equation_count": 0,
        "review_required_equation_count": equation_count,
        "chunk_text_eligible_equation_count": 0,
        "explicit_unreviewed_equation_count": equation_count,
        "unique_equation_identity_count": len(equation_ids),
        "referenced_media_count": len(media_paths),
    }
    validation = {
        **validation_body,
        "validation_id": identity(
            "reference-reading-corpus-coverage-validation", validation_body
        ),
    }
    validation_content = (
        json.dumps(
            validation, ensure_ascii=False, indent=2, sort_keys=True
        ).encode()
        + b"\n"
    )
    validation_status = create_once(
        OUTPUT / "validation.json", validation_content
    )

    previous_pending_summary_bytes = exact(
        PREVIOUS_PENDING / "summary-all.json"
    )
    previous_pending_summary = json.loads(previous_pending_summary_bytes)
    previous_pending_body = dict(previous_pending_summary)
    previous_pending_collection_id = previous_pending_body.pop(
        "reading_transcript_collection_id"
    )
    if (
        previous_pending_collection_id
        != identity(
            "reference-reading-transcript-collection", previous_pending_body
        )
        or previous_pending_collection_id
        != pending_summary["semantic_authority_collection_id"]
    ):
        raise RuntimeError("previous reading collection identity differs")
    pending_supersession_body = {
        "contract_version": "1.0",
        "status": "superseded",
        "usable_as_authority": False,
        "superseded_collection_id": previous_pending_collection_id,
        "superseded_summary_sha256": digest(previous_pending_summary_bytes),
        "replacement_collection_id": pending_summary[
            "reading_transcript_collection_id"
        ],
        "replacement_summary_sha256": digest(pending_summary_bytes),
        "replacement_validation_id": pending_validation["validation_id"],
        "semantic_equivalence_status": "equivalent",
    }
    pending_supersession = {
        **pending_supersession_body,
        "supersession_id": identity(
            "reference-reading-transcript-supersession",
            pending_supersession_body,
        ),
    }
    pending_supersession_status = create_once(
        PREVIOUS_PENDING / "SUPERSEDED.json",
        json.dumps(
            pending_supersession,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode()
        + b"\n",
    )
    coverage_supersession_body = {
        "contract_version": "1.0",
        "status": "superseded",
        "usable_as_authority": False,
        "superseded_coverage_inventory_id": previous_coverage_id,
        "superseded_coverage_sha256": digest(previous_coverage_bytes),
        "replacement_coverage_inventory_id": value["coverage_inventory_id"],
        "replacement_coverage_sha256": digest(content),
        "replacement_validation_id": validation["validation_id"],
        "semantic_equivalence_status": "equivalent",
    }
    coverage_supersession = {
        **coverage_supersession_body,
        "supersession_id": identity(
            "reference-reading-corpus-coverage-supersession",
            coverage_supersession_body,
        ),
    }
    coverage_supersession_status = create_once(
        PREVIOUS_COVERAGE / "SUPERSEDED.json",
        json.dumps(
            coverage_supersession,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode()
        + b"\n",
    )
    for directory in [
        OUTPUT,
        *[path for path in OUTPUT.rglob("*") if path.is_dir()],
    ]:
        if (
            directory.is_symlink()
            or stat.S_IMODE(directory.stat().st_mode) != 0o700
        ):
            raise RuntimeError(
                f"output directory permissions differ: {directory}"
            )
    for path in [path for path in OUTPUT.rglob("*") if path.is_file()]:
        if path.is_symlink() or stat.S_IMODE(path.stat().st_mode) != 0o600:
            raise RuntimeError(f"output file permissions differ: {path}")
    print(
        json.dumps(
            {
                "status": status,
                "validation_status": validation_status,
                "validation_id": validation["validation_id"],
                "validation_sha256": digest(validation_content),
                "pending_supersession_status": pending_supersession_status,
                "pending_supersession_id": pending_supersession[
                    "supersession_id"
                ],
                "coverage_supersession_status": coverage_supersession_status,
                "coverage_supersession_id": coverage_supersession[
                    "supersession_id"
                ],
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
