#!/Users/eugene/repos/projectkoios-ingestion/.venv/bin/python
from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

PREPARATION = Path(
    "/Users/eugene/projects/projectkoios/artifacts/reference-multimodal-preparation-v2"
)
ROOT = Path(
    "/Users/eugene/projects/projectkoios/artifacts/reference-reading-transcripts-v2"
)
SUPERSEDED = Path(
    "/Users/eugene/projects/projectkoios/artifacts/reference-reading-transcripts-v1/SUPERSEDED.json"
)


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def identity(namespace: str, value: object) -> str:
    return f"{namespace}:sha256:{digest(canonical(value))}"


def exact(path: Path, mode: int = 0o600) -> bytes:
    if (
        path.is_symlink()
        or not path.is_file()
        or stat.S_IMODE(path.stat().st_mode) != mode
    ):
        raise RuntimeError(f"missing or unsafe file: {path}")
    return path.read_bytes()


def create_once(path: Path, content: bytes) -> str:
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


def main() -> None:
    for directory in [
        ROOT,
        *[path for path in ROOT.rglob("*") if path.is_dir()],
    ]:
        if (
            directory.is_symlink()
            or stat.S_IMODE(directory.stat().st_mode) != 0o700
        ):
            raise RuntimeError(f"unsafe directory: {directory}")
    superseded = json.loads(exact(SUPERSEDED))
    if (
        superseded["status"] != "superseded"
        or superseded["usable_as_authority"] is not False
    ):
        raise RuntimeError("v1 supersession marker differs")
    summary_bytes = exact(ROOT / "summary-all.json")
    summary = json.loads(summary_bytes)
    collection_id = summary.pop("reading_transcript_collection_id")
    if collection_id != identity(
        "reference-reading-transcript-collection", summary
    ):
        raise RuntimeError("collection identity differs")
    summary["reading_transcript_collection_id"] = collection_id
    deferral_bytes = exact(
        PREPARATION / "equation-recognition-deferral-v1.json"
    )
    deferral = json.loads(deferral_bytes)
    deferral_id = deferral.pop("deferral_inventory_id")
    if deferral_id != identity(
        "reference-multimodal-equation-recognition-deferral-inventory", deferral
    ):
        raise RuntimeError("deferral identity differs")
    deferral["deferral_inventory_id"] = deferral_id
    if (
        digest(deferral_bytes) != summary["equation_deferral_inventory_sha256"]
        or deferral_id != summary["equation_deferral_inventory_id"]
    ):
        raise RuntimeError("collection deferral binding differs")
    deferred_ids = {record["assembly_id"] for record in deferral["records"]}
    if len(deferred_ids) != 1906:
        raise RuntimeError("deferred equation identity coverage differs")

    seen_equations: set[str] = set()
    referenced_members: set[str] = set()
    total_pages = 0
    total_bytes = 0
    total_equations = 0
    total_figures = 0
    total_tables: set[str] = set()
    for member in summary["books"]:
        book_root = ROOT / member["book"]
        book_summary_bytes = exact(book_root / "summary.json")
        if (
            digest(book_summary_bytes) != member["summary_sha256"]
            or len(book_summary_bytes) != member["summary_bytes"]
        ):
            raise RuntimeError(f"{member['book']}: summary member differs")
        book_summary = json.loads(book_summary_bytes)
        transcript_id = book_summary.pop("reading_transcript_id")
        if (
            transcript_id
            != identity("reference-reading-transcript", book_summary)
            or transcript_id != member["reading_transcript_id"]
        ):
            raise RuntimeError(f"{member['book']}: transcript identity differs")
        book_summary["reading_transcript_id"] = transcript_id
        transcript_bytes = exact(book_root / "reading-transcript.jsonl")
        if (
            digest(transcript_bytes) != member["transcript_sha256"]
            or len(transcript_bytes) != member["transcript_utf8_bytes"]
        ):
            raise RuntimeError(f"{member['book']}: transcript bytes differ")
        lines = transcript_bytes.splitlines()
        if len(lines) != member["page_count"]:
            raise RuntimeError(f"{member['book']}: page line coverage differs")
        selected_counts: dict[str, int] = {}
        book_equations = 0
        book_figures: set[str] = set()
        book_tables: set[str] = set()
        for page_index, line in enumerate(lines):
            page = json.loads(line)
            page_id = page.pop("reading_page_id")
            if page_id != identity("reference-reading-transcript-page", page):
                raise RuntimeError(
                    f"{member['book']} page {page_index}: identity differs"
                )
            page["reading_page_id"] = page_id
            if (
                page["page_index"] != page_index
                or page["physical_page"] != page_index + 1
            ):
                raise RuntimeError(
                    f"{member['book']} page {page_index}: order differs"
                )
            text = page["text_evidence"]
            native = text["native_text"]
            native_payload = native["text"].encode()
            if (
                digest(native_payload) != native["text_sha256"]
                or len(native_payload) != native["text_utf8_byte_length"]
            ):
                raise RuntimeError(
                    f"{member['book']} page {page_index}: native evidence differs"
                )
            selected = text["reading_selection"]
            selected_counts[selected] = selected_counts.get(selected, 0) + 1
            ocr = text["selected_ocr_text"]
            if selected == "native_text":
                if ocr is not None:
                    raise RuntimeError(
                        f"{member['book']} page {page_index}: native selection has OCR"
                    )
            elif selected == "selected_ocr_text":
                if ocr is None or ocr["accepted"] is not False:
                    raise RuntimeError(
                        f"{member['book']} page {page_index}: selected OCR semantics differ"
                    )
                payload = ocr["text"].encode()
                if (
                    digest(payload) != ocr["text_sha256"]
                    or len(payload) != ocr["text_utf8_byte_length"]
                ):
                    raise RuntimeError(
                        f"{member['book']} page {page_index}: OCR evidence differs"
                    )
            else:
                raise RuntimeError(
                    f"{member['book']} page {page_index}: selection differs"
                )
            visuals = page["visual_evidence"]
            if [item["visual_order"] for item in visuals] != list(
                range(len(visuals))
            ):
                raise RuntimeError(
                    f"{member['book']} page {page_index}: visual order differs"
                )
            for visual in visuals:
                for rendered in visual["rendered_members"]:
                    path = PREPARATION / rendered["path"]
                    content = exact(path)
                    if (
                        digest(content) != rendered["sha256"]
                        or len(content) != rendered["bytes"]
                    ):
                        raise RuntimeError(
                            f"referenced evidence differs: {path}"
                        )
                    referenced_members.add(rendered["path"])
                if (
                    visual["accepted"] is not False
                    or visual["review_required"] is not True
                ):
                    raise RuntimeError("visual review semantics differ")
                if visual["evidence_type"] == "equation":
                    assembly_id = visual["assembly_id"]
                    if (
                        assembly_id in seen_equations
                        or assembly_id not in deferred_ids
                    ):
                        raise RuntimeError(
                            "equation deferral projection differs"
                        )
                    if (
                        visual["recognized_latex"] is not None
                        or visual["recognized_mathml"] is not None
                    ):
                        raise RuntimeError(
                            "generated equation text entered transcript"
                        )
                    if (
                        visual["chunk_text_eligible"] is not False
                        or visual["recognition_status"]
                        != "not_requested_processor_unsuitable"
                    ):
                        raise RuntimeError(
                            "equation eligibility semantics differ"
                        )
                    seen_equations.add(assembly_id)
                    book_equations += 1
                elif visual["evidence_type"] == "figure":
                    book_figures.add(visual["candidate_id"])
                elif visual["evidence_type"] == "table":
                    book_tables.add(visual["candidate_id"])
                else:
                    raise RuntimeError("unsupported visual evidence type")
        expected_counts = {
            key: count
            for key, count in {
                "native_text": book_summary["selected_source_counts"].get(
                    "native", 0
                ),
                "selected_ocr_text": book_summary["selected_source_counts"].get(
                    "ocr", 0
                ),
            }.items()
            if count
        }
        if selected_counts != expected_counts:
            raise RuntimeError(f"{member['book']}: selected text counts differ")
        if (
            book_equations != member["equation_evidence_count"]
            or len(book_figures) != member["figure_evidence_count"]
            or len(book_tables) != member["table_evidence_count"]
        ):
            raise RuntimeError(
                f"{member['book']}: visual evidence counts differ"
            )
        total_pages += len(lines)
        total_bytes += len(transcript_bytes)
        total_equations += book_equations
        total_figures += len(book_figures)
        total_tables.update(
            f"{member['book']}:{value}" for value in book_tables
        )
    if seen_equations != deferred_ids:
        raise RuntimeError("deferred equations are not projected exactly once")
    if (
        total_pages != summary["page_count"]
        or total_bytes != summary["transcript_utf8_bytes"]
        or total_equations != summary["equation_evidence_count"]
        or total_figures != summary["figure_evidence_count"]
        or len(total_tables) != summary["table_evidence_count"]
    ):
        raise RuntimeError("collection totals differ")
    body = {
        "contract_version": "1.0",
        "status": "valid",
        "reading_transcript_collection_id": collection_id,
        "summary_sha256": digest(summary_bytes),
        "equation_deferral_inventory_id": deferral_id,
        "equation_deferral_inventory_sha256": digest(deferral_bytes),
        "book_count": len(summary["books"]),
        "page_count": total_pages,
        "equation_evidence_count": total_equations,
        "figure_evidence_count": total_figures,
        "table_evidence_count": len(total_tables),
        "referenced_rendered_member_count": len(referenced_members),
        "recognized_equation_text_count": 0,
        "accepted_equation_count": 0,
        "chunk_text_eligible_equation_count": 0,
        "superseded_v1_id": superseded["supersession_id"],
    }
    value = {
        **body,
        "validation_id": identity(
            "reference-reading-transcript-validation", body
        ),
    }
    content = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode()
        + b"\n"
    )
    status = create_once(ROOT / "validation.json", content)
    print(
        json.dumps(
            {
                "status": status,
                "validation_id": value["validation_id"],
                "validation_sha256": digest(content),
                "reading_transcript_collection_id": collection_id,
                "page_count": total_pages,
                "equation_evidence_count": total_equations,
                "figure_evidence_count": total_figures,
                "table_evidence_count": len(total_tables),
                "referenced_rendered_member_count": len(referenced_members),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    os.umask(0o077)
    main()
