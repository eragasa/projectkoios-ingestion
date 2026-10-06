#!/Users/eugene/repos/projectkoios-ingestion/.venv/bin/python
from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path

from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter

PREPARATION = Path(
    "/Users/eugene/projects/projectkoios/artifacts/reference-multimodal-preparation-v2"
)
REFERENCES = Path("/Users/eugene/projects/projectkoios/references")
RESOLUTION = Path(
    "/Users/eugene/projects/projectkoios/artifacts/reference-page-resolution-v1/objects"
)
OUTPUT = Path(
    "/Users/eugene/projects/projectkoios/artifacts/reference-reading-transcripts-v2"
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


def evidence_position(value: dict[str, object]) -> tuple[float, float]:
    boxes = [
        span["bounding_box"]
        for span in value.get("source_spans", [])
        if span.get("bounding_box") is not None
    ]
    if not boxes:
        return (float("inf"), float("inf"))
    return (
        min(float(box[1]) for box in boxes),
        min(float(box[0]) for box in boxes),
    )


def main() -> None:
    plan_bytes = exact(PREPARATION / "plan.json")
    plan = json.loads(plan_bytes)
    eligibility_bytes = exact(PREPARATION / "equation-eligibility-pilot-1.json")
    eligibility = json.loads(eligibility_bytes)
    audit_bytes = exact(PREPARATION / "pix2tex-output-quality-audit-v5.json")
    audit = json.loads(audit_bytes)
    if (
        audit["recommendation"]
        != "pix2tex_unsuitable_for_unattended_queue_execution_defer_eligible_queue"
    ):
        raise RuntimeError("Pix2Tex suitability decision differs")

    deferral_records = []
    deferral_counts: Counter[str] = Counter()
    deferral_bytes: Counter[str] = Counter()
    for record in eligibility["records"]:
        path = PREPARATION / record["rendered_member"]
        content = exact(path)
        if digest(content) != record["rendered_sha256"]:
            raise RuntimeError(f"equation evidence differs: {path}")
        workflow_status = (
            "deferred_future_recognizer"
            if record["disposition"] == "proposed_isolated_equation"
            else "retained_not_eligible"
        )
        deferral_counts[workflow_status] += 1
        deferral_bytes[workflow_status] += len(content)
        deferral_records.append(
            {
                "assembly_id": record["assembly_id"],
                "book": record["book"],
                "page_index": record["page_index"],
                "rendered_member": record["rendered_member"],
                "rendered_sha256": record["rendered_sha256"],
                "rendered_bytes": len(content),
                "eligibility_disposition": record["disposition"],
                "workflow_status": workflow_status,
                "recognition_status": "not_requested_processor_unsuitable",
                "accepted": False,
                "review_required": True,
                "chunk_text_eligible": False,
            }
        )
    if len(deferral_records) != 1906 or deferral_counts != {
        "deferred_future_recognizer": 662,
        "retained_not_eligible": 1244,
    }:
        raise RuntimeError("equation deferral coverage differs")
    deferral_body = {
        "contract_version": "1.0",
        "source_eligibility_inventory_id": eligibility[
            "eligibility_inventory_id"
        ],
        "source_eligibility_inventory_sha256": digest(eligibility_bytes),
        "output_quality_audit_id": audit["output_quality_audit_id"],
        "output_quality_audit_sha256": digest(audit_bytes),
        "processor_suitability": "unsuitable_for_unattended_execution",
        "record_count": len(deferral_records),
        "status_counts": dict(sorted(deferral_counts.items())),
        "status_rendered_bytes": dict(sorted(deferral_bytes.items())),
        "records": deferral_records,
        "accepted_count": 0,
        "review_required_count": len(deferral_records),
        "chunk_text_eligible_count": 0,
        "model_execution_performed": False,
    }
    deferral = {
        **deferral_body,
        "deferral_inventory_id": identity(
            "reference-multimodal-equation-recognition-deferral-inventory",
            deferral_body,
        ),
    }
    deferral_status, deferral_sha256, deferral_size = json_once(
        PREPARATION / "equation-recognition-deferral-v1.json",
        deferral,
    )
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
                page_index = int(figure["source_spans"][0]["page_index"])
                item = {
                    "evidence_type": "figure",
                    "candidate_id": figure["candidate_id"],
                    "evidence_status": figure["evidence_status"],
                    "confidence": figure["confidence"],
                    "source_label": figure["source_label"],
                    "source_spans": figure["source_spans"],
                    "associations": figure["associations"],
                    "rendered_members": evidence_members,
                    "automated": True,
                    "accepted": False,
                    "review_required": True,
                }
                page_visuals[page_index].append(item)
                visual_ids.add(figure["candidate_id"])
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

        for record in deferral_records:
            if record["book"] != name:
                continue
            assembly = quality_by_assembly.get(record["assembly_id"])
            if assembly is None:
                raise RuntimeError(
                    f"{name}: deferred assembly has no quality evidence"
                )
            path = record["rendered_member"]
            item = {
                "evidence_type": "equation",
                "assembly_id": record["assembly_id"],
                "candidate_ids": assembly["candidate_ids"],
                "eligibility_disposition": record["eligibility_disposition"],
                "workflow_status": record["workflow_status"],
                "recognition_status": record["recognition_status"],
                "native_text_evidence": assembly["sanitized_native_text"],
                "source_labels": assembly["source_labels"],
                "source_spans": assembly["source_spans"],
                "rendered_members": [
                    {
                        "path": path,
                        "sha256": record["rendered_sha256"],
                        "bytes": record["rendered_bytes"],
                    }
                ],
                "recognized_latex": None,
                "recognized_mathml": None,
                "automated": True,
                "accepted": False,
                "review_required": True,
                "chunk_text_eligible": False,
            }
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
            native_text = native_page["text"]
            native_payload = native_text.encode()
            if (
                digest(native_payload) != native_page["text_sha256"]
                or len(native_payload) != native_page["text_utf8_byte_length"]
            ):
                raise RuntimeError(
                    f"{name} page {page_index}: native text differs"
                )
            native_bytes_total += len(native_payload)
            chosen = composed_page["chosen_source"]
            selected_counts[chosen] += 1
            if chosen == "native":
                if composed_page["text"] != native_text:
                    raise RuntimeError(
                        f"{name} page {page_index}: native selection differs"
                    )
                selected_ocr = None
                reading_selection = "native_text"
            elif chosen == "ocr":
                payload = composed_page["text"].encode()
                if (
                    digest(payload) != composed_page["text_sha256"]
                    or len(payload) != composed_page["text_utf8_byte_length"]
                ):
                    raise RuntimeError(
                        f"{name} page {page_index}: selected OCR differs"
                    )
                selected_ocr_bytes_total += len(payload)
                selected_ocr = {
                    "composition_id": composed_page["composition_id"],
                    "text": composed_page["text"],
                    "text_sha256": composed_page["text_sha256"],
                    "text_utf8_byte_length": composed_page[
                        "text_utf8_byte_length"
                    ],
                    "automated": True,
                    "accepted": False,
                }
                reading_selection = "selected_ocr_text"
            else:
                raise RuntimeError(
                    f"{name} page {page_index}: unsupported text source"
                )
            visual_evidence = sorted(
                page_visuals[page_index],
                key=lambda value: (
                    *evidence_position(value),
                    str(value["evidence_type"]),
                    str(value.get("assembly_id", value.get("candidate_id"))),
                ),
            )
            for order, value in enumerate(visual_evidence):
                value["visual_order"] = order
            visual_count += len(visual_evidence)
            page_body = {
                "contract_version": "1.0",
                "book": name,
                "source_sha256": source_sha256,
                "page_index": page_index,
                "physical_page": page_index + 1,
                "printed_page_label": composed_page["printed_page_label"],
                "text_evidence": {
                    "native_text": {
                        "page_id": native_page["page_id"],
                        "text": native_text,
                        "text_sha256": native_page["text_sha256"],
                        "text_utf8_byte_length": native_page[
                            "text_utf8_byte_length"
                        ],
                    },
                    "selected_ocr_text": selected_ocr,
                    "reading_selection": reading_selection,
                    "chunking_status": "not_requested",
                },
                "visual_evidence": visual_evidence,
            }
            page = {
                **page_body,
                "reading_page_id": identity(
                    "reference-reading-transcript-page", page_body
                ),
            }
            lines.append(canonical(page))
        if selected_counts != Counter(book["chosen_source_counts"]):
            raise RuntimeError(f"{name}: selected source counts differ")
        content = b"\n".join(lines) + b"\n"
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
            "equation_deferral_inventory_id": deferral["deferral_inventory_id"],
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
        "equation_deferral_inventory_id": deferral["deferral_inventory_id"],
        "equation_deferral_inventory_sha256": deferral_sha256,
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
    print(
        json.dumps(
            {
                "deferral_status": deferral_status,
                "deferral_inventory_id": deferral["deferral_inventory_id"],
                "deferral_sha256": deferral_sha256,
                "deferral_bytes": deferral_size,
                "summary_status": global_status,
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
