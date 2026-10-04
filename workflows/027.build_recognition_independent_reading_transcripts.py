#!/Users/eugene/repos/projectkoios-ingestion/.venv/bin/python
from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from pathlib import Path

from reading_transcript_equation_evidence import (
    ReadingTranscriptEquationEvidence,
)
from reading_transcript_figure_evidence import (
    ReadingTranscriptFigureEvidence,
)
from reading_transcript_page import ReadingTranscriptPage

PREPARATION = Path(
    "/Users/eugene/projects/projectkoios/artifacts/reference-multimodal-preparation-v2"
)
REFERENCES = Path("/Users/eugene/projects/projectkoios/references")
RESOLUTION = Path(
    "/Users/eugene/projects/projectkoios/artifacts/reference-page-resolution-v1/objects"
)
OUTPUT = Path(
    "/Users/eugene/projects/projectkoios/artifacts/reference-reading-transcripts-v3"
)
AUTHORITY = Path(
    "/Users/eugene/projects/projectkoios/artifacts/reference-reading-transcripts-v2"
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


def json_once(path: Path, value: object) -> tuple[str, str, int]:
    content = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode()
        + b"\n"
    )
    return create_once(path, content), digest(content), len(content)


def main() -> None:
    plan_bytes = exact(PREPARATION / "plan.json")
    plan = json.loads(plan_bytes)
    selection_bytes = exact(PREPARATION / "equation-evidence-selection-v1.json")
    selection = json.loads(selection_bytes)
    selection_body = dict(selection)
    selection_id = selection_body.pop("selection_inventory_id")
    if selection_id != identity(
        "reference-equation-evidence-selection-inventory", selection_body
    ):
        raise RuntimeError("equation evidence selection identity differs")
    selected_records = [
        record
        for record in selection["records"]
        if record["disposition"] == "selected_primary_equation_evidence"
    ]
    auxiliary_records = [
        record
        for record in selection["records"]
        if record["disposition"] == "retained_auxiliary_equation_evidence"
    ]
    if (
        len(selected_records) != 1906
        or len(auxiliary_records) != 3454
        or selection["recognized_text_retained_count"] != 0
        or selection["model_execution_performed"] is not False
    ):
        raise RuntimeError("equation evidence selection coverage differs")
    authority_summary_bytes = exact(AUTHORITY / "summary-all.json")
    authority_summary = json.loads(authority_summary_bytes)
    authority_body = dict(authority_summary)
    authority_collection_id = authority_body.pop(
        "reading_transcript_collection_id"
    )
    if authority_collection_id != identity(
        "reference-reading-transcript-collection", authority_body
    ):
        raise RuntimeError("authority collection identity differs")
    authority_books = {
        member["book"]: member for member in authority_summary["books"]
    }
    book_summaries = []
    for book in plan["books"]:
        name = book["book"]
        source_sha256 = book["source_sha256"]
        pages = int(book["page_count"])
        native_path = REFERENCES / source_sha256 / "transcript.json"
        native_bytes = exact(native_path)
        native = json.loads(native_bytes)
        composed_path = (
            RESOLUTION
            / source_sha256[:2]
            / source_sha256
            / "composed-transcript.json"
        )
        composed_bytes = exact(composed_path)
        composed = json.loads(composed_bytes)
        if digest(native_bytes) != book["native_transcript_sha256"]:
            raise RuntimeError(f"{name}: native transcript differs")
        if digest(composed_bytes) != book["composed_transcript_sha256"]:
            raise RuntimeError(f"{name}: composed transcript differs")
        if len(native["pages"]) != pages or len(composed["pages"]) != pages:
            raise RuntimeError(f"{name}: text page coverage differs")

        quality_by_assembly = {}
        members = {}
        page_visuals: dict[int, list[dict[str, object]]] = {
            index: [] for index in range(pages)
        }
        visual_ids: set[str] = set()
        rendered_paths: set[str] = set()
        figure_count = 0
        table_count = 0
        table_region_count = 0
        equation_count = 0
        for chunk in book["chunks"]:
            number = int(chunk["chunk_number"])
            chunk_root = (
                PREPARATION / "books" / name / "chunks" / f"chunk-{number:03d}"
            )
            inventory = json.loads(exact(chunk_root / "inventory.json"))
            quality = json.loads(exact(chunk_root / "quality-inventory.json"))
            if (
                inventory["chunk_plan_id"] != chunk["chunk_plan_id"]
                or quality["chunk_plan_id"] != chunk["chunk_plan_id"]
            ):
                raise RuntimeError(
                    f"{name} chunk {number}: plan binding differs"
                )
            for member in inventory["members"]:
                relative = str(
                    (chunk_root / member["path"]).relative_to(PREPARATION)
                )
                content = exact(PREPARATION / relative)
                if (
                    len(content) != member["bytes"]
                    or digest(content) != member["sha256"]
                ):
                    raise RuntimeError(f"{name} chunk {number}: member differs")
                members[relative] = member
            for assembly in quality["equation_assemblies"]:
                quality_by_assembly[assembly["assembly_id"]] = assembly
            for figure in quality["figures"]:
                evidence_paths = [
                    str((chunk_root / member).relative_to(PREPARATION))
                    for member in figure["rendered_members"]
                ]
                evidence_members = []
                for path in evidence_paths:
                    member = members[path]
                    evidence_members.append(
                        {
                            "path": path,
                            "sha256": member["sha256"],
                            "bytes": member["bytes"],
                        }
                    )
                    rendered_paths.add(path)
                figure_record = (
                    ReadingTranscriptFigureEvidence.from_quality_evidence(
                        figure_evidence=figure,
                        rendered_members=evidence_members,
                    )
                )
                page_visuals[figure_record.page_index].append(
                    figure_record.to_record()
                )
                visual_ids.add(figure_record.candidate_id)
                figure_count += 1
            for table in quality["tables"]:
                by_page: dict[int, list[dict[str, object]]] = {}
                for member_name in table["rendered_members"]:
                    path = str(
                        (chunk_root / member_name).relative_to(PREPARATION)
                    )
                    member = members[path]
                    member_value = {
                        "path": path,
                        "sha256": member["sha256"],
                        "bytes": member["bytes"],
                        "region_evidence_id": member["region_evidence_id"],
                    }
                    by_page.setdefault(int(member["page_index"]), []).append(
                        member_value
                    )
                    rendered_paths.add(path)
                    table_region_count += 1
                for page_index, evidence_members in sorted(by_page.items()):
                    spans = [
                        span
                        for span in table["source_spans"]
                        if int(span["page_index"]) == page_index
                    ]
                    item = {
                        "evidence_type": "table",
                        "candidate_id": table["candidate_id"],
                        "evidence_status": table["evidence_status"],
                        "confidence": table["confidence"],
                        "boundary_kind": table["boundary_kind"],
                        "source_label": table["source_label"],
                        "source_spans": spans,
                        "associations": table["associations"],
                        "rendered_members": evidence_members,
                        "automated": True,
                        "accepted": False,
                        "review_required": True,
                    }
                    page_visuals[page_index].append(item)
                visual_ids.add(table["candidate_id"])
                table_count += 1

        for record in selected_records:
            if record["book"] != name:
                continue
            assembly = quality_by_assembly.get(record["assembly_id"])
            if assembly is None:
                raise RuntimeError(
                    f"{name}: selected assembly has no quality evidence"
                )
            equation = ReadingTranscriptEquationEvidence.from_selected_evidence(
                selection_record=record,
                assembly_evidence=assembly,
                selection_inventory_id=selection_id,
            )
            rendered = record["assembly_rendered_member"]
            path = rendered["path"]
            content = exact(PREPARATION / path)
            if (
                len(content) != rendered["bytes"]
                or digest(content) != rendered["sha256"]
            ):
                raise RuntimeError(f"{name}: selected assembly image differs")
            item = equation.to_record()
            page_visuals[int(record["page_index"])].append(item)
            visual_ids.add(record["assembly_id"])
            rendered_paths.add(path)
            equation_count += 1

        selected_counts: Counter[str] = Counter()
        lines = []
        native_bytes_total = 0
        selected_ocr_bytes_total = 0
        visual_count = 0
        for page_index in range(pages):
            native_page = native["pages"][page_index]
            composed_page = composed["pages"][page_index]
            page = ReadingTranscriptPage.compose(
                book=name,
                source_sha256=source_sha256,
                page_index=page_index,
                native_page=native_page,
                composed_page=composed_page,
                visual_evidence=page_visuals[page_index],
            )
            selected_counts[page.selected_source] += 1
            native_bytes_total += page.native_text_utf8_bytes
            selected_ocr_bytes_total += page.selected_ocr_text_utf8_bytes
            visual_count += page.visual_evidence_count
            lines.append(page.canonical_bytes)
        if selected_counts != Counter(book["chosen_source_counts"]):
            raise RuntimeError(f"{name}: selected source counts differ")
        content = b"\n".join(lines) + b"\n"
        authority_member = authority_books.get(name)
        if authority_member is None:
            raise RuntimeError(f"{name}: authority member is missing")
        authority_content = exact(AUTHORITY / name / "reading-transcript.jsonl")
        if digest(authority_content) != authority_member["transcript_sha256"]:
            raise RuntimeError(f"{name}: authority transcript differs")
        authority_lines = authority_content.splitlines()
        if len(authority_lines) != len(lines):
            raise RuntimeError(f"{name}: authority page coverage differs")
        equation_semantic_keys = (
            "evidence_type",
            "assembly_id",
            "candidate_ids",
            "native_text_evidence",
            "source_labels",
            "source_spans",
            "rendered_members",
            "recognized_latex",
            "recognized_mathml",
            "automated",
            "accepted",
            "review_required",
            "chunk_text_eligible",
            "visual_order",
        )
        for page_index, (line, authority_line) in enumerate(
            zip(lines, authority_lines, strict=True)
        ):
            page = json.loads(line)
            authority_page = json.loads(authority_line)
            for key in (
                "contract_version",
                "book",
                "source_sha256",
                "page_index",
                "physical_page",
                "printed_page_label",
                "text_evidence",
            ):
                if page[key] != authority_page[key]:
                    raise RuntimeError(
                        f"{name} page {page_index}: authority {key} differs"
                    )
            visuals = page["visual_evidence"]
            authority_visuals = authority_page["visual_evidence"]
            if len(visuals) != len(authority_visuals):
                raise RuntimeError(
                    f"{name} page {page_index}: authority visual coverage differs"
                )
            for visual, authority_visual in zip(
                visuals, authority_visuals, strict=True
            ):
                if visual["evidence_type"] != authority_visual["evidence_type"]:
                    raise RuntimeError(
                        f"{name} page {page_index}: authority visual order differs"
                    )
                if visual["evidence_type"] == "equation":
                    if any(
                        visual[key] != authority_visual[key]
                        for key in equation_semantic_keys
                    ):
                        raise RuntimeError(
                            f"{name} page {page_index}: authority equation evidence differs"
                        )
                elif visual != authority_visual:
                    raise RuntimeError(
                        f"{name} page {page_index}: authority visual evidence differs"
                    )
        transcript_path = OUTPUT / name / "reading-transcript.jsonl"
        create_once(transcript_path, content)
        transcript_sha256 = digest(content)
        summary_body = {
            "contract_version": "1.0",
            "book": name,
            "source_sha256": source_sha256,
            "page_count": pages,
            "native_transcript_sha256": digest(native_bytes),
            "composed_transcript_id": composed["composed_transcript_id"],
            "composed_transcript_sha256": digest(composed_bytes),
            "selected_source_counts": dict(sorted(selected_counts.items())),
            "native_text_utf8_bytes": native_bytes_total,
            "selected_ocr_text_utf8_bytes": selected_ocr_bytes_total,
            "equation_evidence_count": equation_count,
            "figure_evidence_count": figure_count,
            "table_evidence_count": table_count,
            "table_region_evidence_count": table_region_count,
            "visual_evidence_record_count": visual_count,
            "unique_visual_identity_count": len(visual_ids),
            "referenced_rendered_member_count": len(rendered_paths),
            "transcript_path": str(transcript_path.relative_to(OUTPUT)),
            "transcript_sha256": transcript_sha256,
            "transcript_utf8_bytes": len(content),
            "semantic_authority_transcript_sha256": digest(authority_content),
            "semantic_equivalence_status": "equivalent",
            "equation_evidence_selection_inventory_id": selection_id,
            "equation_evidence_selection_inventory_sha256": digest(
                selection_bytes
            ),
            "model_execution_performed": False,
            "search_indexing_performed": False,
            "publication_performed": False,
            "limitations": [
                "automated_unreviewed_visual_evidence",
                "equations_unaccepted_and_chunk_text_ineligible",
                "no_generated_equation_latex_or_mathml",
                "text_chunking_not_requested",
                "native_and_selected_ocr_evidence_retained_separately",
            ],
        }
        summary = {
            **summary_body,
            "reading_transcript_id": identity(
                "reference-reading-transcript", summary_body
            ),
        }
        summary_status, summary_sha256, summary_size = json_once(
            OUTPUT / name / "summary.json",
            summary,
        )
        book_summaries.append(
            {
                "book": name,
                "reading_transcript_id": summary["reading_transcript_id"],
                "transcript_sha256": transcript_sha256,
                "transcript_utf8_bytes": len(content),
                "summary_sha256": summary_sha256,
                "summary_bytes": summary_size,
                "page_count": pages,
                "equation_evidence_count": equation_count,
                "figure_evidence_count": figure_count,
                "table_evidence_count": table_count,
            }
        )

    global_body = {
        "contract_version": "1.0",
        "preparation_plan_id": plan["plan_id"],
        "preparation_plan_sha256": digest(plan_bytes),
        "equation_evidence_selection_inventory_id": selection_id,
        "equation_evidence_selection_inventory_sha256": digest(selection_bytes),
        "semantic_authority_collection_id": authority_collection_id,
        "semantic_authority_summary_sha256": digest(authority_summary_bytes),
        "semantic_equivalence_status": "equivalent",
        "book_count": len(book_summaries),
        "page_count": sum(item["page_count"] for item in book_summaries),
        "equation_evidence_count": sum(
            item["equation_evidence_count"] for item in book_summaries
        ),
        "figure_evidence_count": sum(
            item["figure_evidence_count"] for item in book_summaries
        ),
        "table_evidence_count": sum(
            item["table_evidence_count"] for item in book_summaries
        ),
        "transcript_utf8_bytes": sum(
            item["transcript_utf8_bytes"] for item in book_summaries
        ),
        "books": book_summaries,
        "model_execution_performed": False,
        "database_projection_performed": False,
        "search_indexing_performed": False,
        "publication_performed": False,
    }
    global_summary = {
        **global_body,
        "reading_transcript_collection_id": identity(
            "reference-reading-transcript-collection", global_body
        ),
    }
    global_status, global_sha256, global_size = json_once(
        OUTPUT / "summary-all.json", global_summary
    )
    validation_body = {
        "contract_version": "1.0",
        "status": "valid",
        "reading_transcript_collection_id": global_summary[
            "reading_transcript_collection_id"
        ],
        "summary_sha256": global_sha256,
        "equation_evidence_selection_inventory_id": selection_id,
        "equation_evidence_selection_inventory_sha256": digest(selection_bytes),
        "semantic_authority_collection_id": authority_collection_id,
        "semantic_authority_summary_sha256": digest(authority_summary_bytes),
        "semantic_equivalence_status": "equivalent",
        "book_count": global_summary["book_count"],
        "page_count": global_summary["page_count"],
        "equation_evidence_count": global_summary["equation_evidence_count"],
        "figure_evidence_count": global_summary["figure_evidence_count"],
        "table_evidence_count": global_summary["table_evidence_count"],
        "recognized_equation_text_count": 0,
        "accepted_equation_count": 0,
        "chunk_text_eligible_equation_count": 0,
    }
    validation = {
        **validation_body,
        "validation_id": identity(
            "reference-reading-transcript-validation", validation_body
        ),
    }
    validation_status, validation_sha256, validation_size = json_once(
        OUTPUT / "validation.json", validation
    )
    print(
        json.dumps(
            {
                "equation_evidence_selection_inventory_id": selection_id,
                "equation_evidence_selection_inventory_sha256": digest(
                    selection_bytes
                ),
                "summary_status": global_status,
                "validation_status": validation_status,
                "validation_id": validation["validation_id"],
                "validation_sha256": validation_sha256,
                "validation_bytes": validation_size,
                "reading_transcript_collection_id": global_summary[
                    "reading_transcript_collection_id"
                ],
                "summary_sha256": global_sha256,
                "summary_bytes": global_size,
                "book_count": global_summary["book_count"],
                "page_count": global_summary["page_count"],
                "equation_evidence_count": global_summary[
                    "equation_evidence_count"
                ],
                "figure_evidence_count": global_summary[
                    "figure_evidence_count"
                ],
                "table_evidence_count": global_summary["table_evidence_count"],
                "transcript_utf8_bytes": global_summary[
                    "transcript_utf8_bytes"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    os.umask(0o077)
    main()
