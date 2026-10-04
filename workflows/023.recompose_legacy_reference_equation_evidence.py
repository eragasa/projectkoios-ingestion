#!/Users/eugene/repos/projectkoios-ingestion/.venv/bin/python
from __future__ import annotations

import hashlib
import json
import os
import stat
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

from projectkoios.ingestion.page_projection import (
    PageProjectionPlanEntry,
    page_projection_validation_report_bytes,
    validate_page_projection,
)

ARTIFACTS = Path("/Users/eugene/projects/projectkoios/artifacts")
LEGACY = ARTIFACTS / "reference-multimodal-v1"
OUTPUT = ARTIFACTS / "reference-legacy-reading-transcripts-v3"
REFERENCES = Path("/Users/eugene/projects/projectkoios/references")
BASELINES = ARTIFACTS / "reference-page-resolution-v1" / "objects"
PNG = b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True)
class Book:
    document_id: str
    name: str
    filename: str
    title: str
    digest: str
    pages: int
    chunks: int
    chunk_pages: int
    item_file: str
    expected_candidates: int
    expected_assemblies: int
    expected_selected: int


BOOKS = (
    Book(
        "doc-01",
        "Kittel8ed",
        "Kittel8ed.pdf",
        "Introduction to Solid State Physics",
        "7c177d8ce281eeb1a1e0897e8d711bd908c2657ec42abd690ff1105533b7a6ed",
        700,
        70,
        10,
        "structured-transcription.json",
        294,
        268,
        241,
    ),
    Book(
        "doc-02",
        "SimonSS1Ed",
        "SimonSS1Ed.pdf",
        "The Oxford Solid State Basics",
        "46807198536b8672000463b8d9c8ae555f4955ba0ad0e80cec19b01671030be2",
        305,
        31,
        10,
        "projection.json",
        1169,
        914,
        367,
    ),
    Book(
        "doc-03",
        "AshcroftMermin_SolidStatePhysics",
        "AshcroftMermin_SolidStatePhysics.pdf",
        "Solid State Physics",
        "6299153bde8e4ee49583ca8abfcc9afd687a34c25a0d06252681200fbda781ad",
        848,
        85,
        10,
        "projection.json",
        1581,
        1539,
        540,
    ),
    Book(
        "doc-04",
        "Marder2Ed",
        "Marder2Ed.pdf",
        "Condensed Matter Physics",
        "bc1ce37437da489aa1b35b5fe86750cf3bd35a9c0c9df7597b1e55871a243d93",
        985,
        99,
        10,
        "projection.json",
        2084,
        1951,
        883,
    ),
    Book(
        "doc-05",
        "SzeNg3Ed",
        "SzeNg3Ed.pdf",
        "Physics of Semiconductor Devices",
        "7909c81fe5c12006dbaf4f664b029b67319bd7c45fe86d97ccedaf229067a221",
        763,
        77,
        10,
        "projection.json",
        882,
        861,
        254,
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


def compact(value: str) -> str:
    return " ".join(value.split())


def overlaps(box: list[float], region: list[float]) -> bool:
    x0, y0, x1, y1 = box
    rx0, ry0, rx1, ry1 = region
    center_inside = rx0 <= (x0 + x1) / 2 <= rx1 and ry0 <= (y0 + y1) / 2 <= ry1
    intersection = max(0.0, min(x1, rx1) - max(x0, rx0)) * max(
        0.0, min(y1, ry1) - max(y0, ry0)
    )
    area = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    return center_inside or (area > 0 and intersection / area >= 0.5)


def recompose(book: Book) -> dict[str, object]:
    legacy_root = LEGACY / book.name
    output_root = OUTPUT / book.name
    source_path = REFERENCES / book.digest / "document.pdf"
    baseline_path = (
        BASELINES / book.digest[:2] / book.digest / "composed-transcript.json"
    )
    source = exact(source_path)
    if digest(source) != book.digest:
        raise RuntimeError(f"{book.name}: source digest differs")
    baseline = json.loads(exact(baseline_path))
    if (
        baseline["page_count"] != book.pages
        or len(baseline["pages"]) != book.pages
    ):
        raise RuntimeError(f"{book.name}: baseline coverage differs")
    old_transcript = exact(legacy_root / "reading-transcript.jsonl")
    old_pages = [json.loads(line) for line in old_transcript.splitlines()]
    if len(old_pages) != book.pages:
        raise RuntimeError(f"{book.name}: legacy transcript coverage differs")

    chunk_data: dict[int, dict[str, object]] = {}
    selection_records = []
    selection_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    tier_counts: Counter[str] = Counter()
    candidate_memberships = 0
    selected_ids: set[str] = set()
    selected_bytes = 0
    for chunk in range(1, book.chunks + 1):
        chunk_root = legacy_root / "chunks" / f"chunk-{chunk:03d}"
        items_bytes = exact(chunk_root / book.item_file)
        item_value = json.loads(items_bytes)
        items = item_value["items"]
        enrichment = chunk_root / "equation-enrichment"
        equations = []
        if (enrichment / "index.json").is_file():
            index_bytes = exact(enrichment / "index.json")
            recognition_bytes = exact(enrichment / "recognition.json")
            index = json.loads(index_bytes)
            recognition = json.loads(recognition_bytes)
            proposals = {
                item["assembly_id"]: item for item in recognition["proposals"]
            }
            if len(proposals) != len(index["records"]):
                raise RuntimeError(
                    f"{book.name} chunk {chunk}: recognition coverage differs"
                )
            for ordinal, record in enumerate(index["records"], 1):
                proposal = proposals[record["assembly_id"]]
                tier = record["tier"]
                status = proposal["status"]
                selected = (
                    status in ("proposed", "failed") and tier != "rejected"
                )
                disposition = (
                    "selected_primary_equation_evidence"
                    if selected
                    else (
                        "retained_rejected_evidence"
                        if tier == "rejected"
                        else "retained_auxiliary_evidence"
                    )
                )
                image = exact(enrichment / f"assembly-{ordinal:03d}.png")
                if (
                    not image.startswith(PNG)
                    or digest(image) != record["rendered_region_sha256"]
                ):
                    raise RuntimeError(
                        f"{book.name} chunk {chunk} assembly {ordinal}: image differs"
                    )
                candidate_memberships += len(record["candidate_ids"])
                selection_counts[disposition] += 1
                status_counts[status] += 1
                tier_counts[tier] += 1
                relative = None
                if selected:
                    relative = f"evidence/equations/chunk-{chunk:03d}/assembly-{ordinal:03d}.png"
                    create_once(output_root / relative, image)
                    selected_ids.add(record["assembly_id"])
                    selected_bytes += len(image)
                global_page = (chunk - 1) * book.chunk_pages + int(
                    record["page_index"]
                )
                selection = {
                    "assembly_id": record["assembly_id"],
                    "chunk_number": chunk,
                    "ordinal": ordinal,
                    "page_index": global_page,
                    "candidate_ids": record["candidate_ids"],
                    "source_block_ids": record["source_block_ids"],
                    "source_bounding_box": record["source_bounding_box"],
                    "rendered_sha256": digest(image),
                    "rendered_bytes": len(image),
                    "historical_index_tier": tier,
                    "historical_recognition_status": status,
                    "transcript_disposition": disposition,
                    "transcript_rendered_member": relative,
                    "review_status": "unreviewed",
                    "accepted": False,
                    "review_required": True,
                    "chunk_text_eligible": False,
                    "recognized_text_retained": False,
                }
                selection_records.append(selection)
                equations.append((record, selection))
        chunk_data[chunk] = {
            "items": items,
            "equations": equations,
            "items_sha256": digest(items_bytes),
        }

    if (
        len(selection_records) != book.expected_assemblies
        or candidate_memberships != book.expected_candidates
    ):
        raise RuntimeError(f"{book.name}: assembly coverage differs")
    if (
        selection_counts["selected_primary_equation_evidence"]
        != book.expected_selected
    ):
        raise RuntimeError(f"{book.name}: selected equation coverage differs")
    inventory_body = {
        "contract_version": "1.0",
        "document_id": book.document_id,
        "book": book.name,
        "source_sha256": book.digest,
        "assembly_count": len(selection_records),
        "candidate_membership_count": candidate_memberships,
        "selected_equation_count": book.expected_selected,
        "historical_index_tier_counts": dict(sorted(tier_counts.items())),
        "historical_recognition_status_counts": dict(
            sorted(status_counts.items())
        ),
        "disposition_counts": dict(sorted(selection_counts.items())),
        "selected_rendered_bytes": selected_bytes,
        "records": selection_records,
        "recognized_text_retained_count": 0,
        "accepted_count": 0,
        "review_status_counts": {"unreviewed": len(selection_records)},
        "review_required_count": len(selection_records),
        "chunk_text_eligible_count": 0,
        "model_execution_performed": False,
    }
    inventory = {
        **inventory_body,
        "selection_inventory_id": identity(
            "reference-legacy-equation-evidence-selection", inventory_body
        ),
    }
    inventory_content = (
        json.dumps(
            inventory, ensure_ascii=False, indent=2, sort_keys=True
        ).encode()
        + b"\n"
    )
    create_once(
        output_root / "equation-evidence-selection.json", inventory_content
    )

    pages = []
    counts: Counter[str] = Counter()
    referenced_equations: set[str] = set()
    referenced_figures: set[str] = set()
    figure_bytes = 0
    for chunk in range(1, book.chunks + 1):
        offset = (chunk - 1) * book.chunk_pages
        values = chunk_data[chunk]
        items_by_page: dict[int, list[dict[str, object]]] = defaultdict(list)
        for item in values["items"]:
            items_by_page[int(item["page_index"])].append(item)
        equations_by_page: dict[
            int, list[tuple[dict[str, object], dict[str, object]]]
        ] = defaultdict(list)
        for record, selection in values["equations"]:
            if (
                selection["transcript_disposition"]
                == "selected_primary_equation_evidence"
            ):
                equations_by_page[int(record["page_index"])].append(
                    (record, selection)
                )
        for local in range(min(book.chunk_pages, book.pages - offset)):
            physical = offset + local + 1
            old_page = old_pages[physical - 1]
            old_blocks = old_page["blocks"]
            used: set[int] = set()
            paragraphs: dict[tuple[str, str | None], deque[int]] = defaultdict(
                deque
            )
            figures: dict[str, int] = {}
            for old_index, block in enumerate(old_blocks):
                if block["type"] == "paragraph":
                    paragraphs[(block["text"], block.get("style"))].append(
                        old_index
                    )
                elif block["type"] == "figure":
                    source_image = legacy_root / block["png_path"]
                    metadata = json.loads(
                        exact(source_image.parent / "metadata.json")
                    )
                    candidate_id = metadata.get("candidate_id")
                    if candidate_id is None:
                        candidate_id = metadata["owner_candidate"][
                            "candidate_id"
                        ]
                    figures[candidate_id] = old_index
            equation_by_candidate: dict[str, dict[str, object]] = {}
            equation_block_ids: set[str] = set()
            equation_boxes: list[list[float]] = []
            for record, selection in equations_by_page.get(local, []):
                block = {
                    "type": "equation",
                    "assembly_id": record["assembly_id"],
                    "candidate_ids": record["candidate_ids"],
                    "latex": None,
                    "mathml": None,
                    "native_text": compact(record["sanitized_native_text"]),
                    "png_path": selection["transcript_rendered_member"],
                    "png_sha256": selection["rendered_sha256"],
                    "status": "recognition_deferred_processor_unsuitable",
                    "historical_recognition_status": selection[
                        "historical_recognition_status"
                    ],
                    "review_status": "unreviewed",
                    "accepted": False,
                    "review_required": True,
                    "chunk_text_eligible": False,
                }
                for candidate_id in record["candidate_ids"]:
                    equation_by_candidate[candidate_id] = block
                equation_block_ids.update(record["source_block_ids"])
                equation_boxes.append(record["source_bounding_box"])
            blocks = []
            emitted_equations: set[int] = set()
            emitted_figures: set[str] = set()
            for item in sorted(
                items_by_page.get(local, []),
                key=lambda value: int(value["order_index"]),
            ):
                kind = item["item_kind"]
                if kind == "page_anchor":
                    continue
                if kind == "equation":
                    equation = equation_by_candidate.get(
                        item["source_object_id"]
                    )
                    if (
                        equation is not None
                        and id(equation) not in emitted_equations
                    ):
                        blocks.append(equation)
                        emitted_equations.add(id(equation))
                    continue
                if kind == "figure":
                    old_index = figures.get(item["source_object_id"])
                    if (
                        old_index is not None
                        and item["source_object_id"] not in emitted_figures
                    ):
                        original = dict(old_blocks[old_index])
                        used.add(old_index)
                        source_image = legacy_root / original["png_path"]
                        image = exact(source_image)
                        if not image.startswith(PNG):
                            raise RuntimeError(
                                f"{book.name}: invalid figure image"
                            )
                        relative = f"evidence/figures/{original['png_path']}"
                        create_once(output_root / relative, image)
                        figure_bytes += len(image)
                        original["png_path"] = relative
                        original["png_sha256"] = digest(image)
                        original.pop("order", None)
                        blocks.append(original)
                        emitted_figures.add(item["source_object_id"])
                        referenced_figures.add(item["source_object_id"])
                    continue
                if kind not in ("prose", "heading") or not item.get(
                    "normalized_text"
                ):
                    continue
                key = (
                    item["normalized_text"],
                    "heading" if kind == "heading" else None,
                )
                queue = paragraphs.get(key)
                if not queue:
                    continue
                old_index = queue.popleft()
                used.add(old_index)
                ids = set(item["source_block_ids"])
                spans = [
                    span["bounding_box"]
                    for span in item["source_spans"]
                    if span["bounding_box"] is not None
                ]
                if ids & equation_block_ids or any(
                    overlaps(box, equation_box)
                    for box in spans
                    for equation_box in equation_boxes
                ):
                    counts["equation_source_paragraphs_suppressed"] += 1
                    continue
                original = dict(old_blocks[old_index])
                original.pop("order", None)
                blocks.append(original)
            for candidate_id, old_index in figures.items():
                if candidate_id in emitted_figures:
                    continue
                original = dict(old_blocks[old_index])
                used.add(old_index)
                source_image = legacy_root / original["png_path"]
                image = exact(source_image)
                relative = f"evidence/figures/{original['png_path']}"
                create_once(output_root / relative, image)
                figure_bytes += len(image)
                original["png_path"] = relative
                original["png_sha256"] = digest(image)
                original.pop("order", None)
                blocks.append(original)
                emitted_figures.add(candidate_id)
                referenced_figures.add(candidate_id)
            for equation_key, equation in {
                id(value): value for value in equation_by_candidate.values()
            }.items():
                if equation_key not in emitted_equations:
                    blocks.append(equation)
                    emitted_equations.add(equation_key)
            for old_index, original_value in enumerate(old_blocks):
                if old_index in used or original_value["type"] == "equation":
                    continue
                if original_value["type"] != "paragraph":
                    raise RuntimeError(
                        f"{book.name}: unsupported unmatched block"
                    )
                original = dict(original_value)
                original.pop("order", None)
                blocks.append(original)
                counts["unmatched_legacy_paragraphs_retained"] += 1
            normalized_paragraphs = {
                compact(block["text"])
                for block in blocks
                if block["type"] == "paragraph"
            }
            for order, block in enumerate(blocks):
                block["order"] = order
                if block["type"] == "equation":
                    if block["assembly_id"] in referenced_equations:
                        raise RuntimeError(
                            f"{book.name}: equation projected twice"
                        )
                    referenced_equations.add(block["assembly_id"])
                    if (
                        block["latex"] is not None
                        or block["mathml"] is not None
                    ):
                        raise RuntimeError(
                            f"{book.name}: recognized equation text retained"
                        )
                    if (
                        block["native_text"]
                        and compact(block["native_text"])
                        in normalized_paragraphs
                    ):
                        raise RuntimeError(
                            f"{book.name}: equation source duplicated as paragraph"
                        )
            counts["paragraphs"] += sum(
                block["type"] == "paragraph" for block in blocks
            )
            counts["headings"] += sum(
                block["type"] == "paragraph" and block.get("style") == "heading"
                for block in blocks
            )
            counts["figures"] += len(emitted_figures)
            counts["primary_equations"] += len(emitted_equations)
            pages.append(
                {
                    "physical_page": physical,
                    "printed_page": baseline["pages"][physical - 1].get(
                        "printed_page_label"
                    ),
                    "citation": {
                        "physical_page": physical,
                        "printed_page": baseline["pages"][physical - 1].get(
                            "printed_page_label"
                        ),
                    },
                    "blocks": blocks,
                }
            )
    if len(pages) != book.pages or referenced_equations != selected_ids:
        raise RuntimeError(f"{book.name}: transcript coverage differs")
    transcript = b"\n".join(canonical(page) for page in pages) + b"\n"
    create_once(output_root / "reading-transcript.jsonl", transcript)
    summary_body = {
        "contract_version": "2.0",
        "status": "complete",
        "document_id": book.document_id,
        "book": book.name,
        "source_sha256": book.digest,
        "pages": book.pages,
        "paragraphs": counts["paragraphs"],
        "headings": counts["headings"],
        "figures": counts["figures"],
        "primary_equations": counts["primary_equations"],
        "equation_source_paragraphs_suppressed": counts[
            "equation_source_paragraphs_suppressed"
        ],
        "unmatched_legacy_paragraphs_retained": counts[
            "unmatched_legacy_paragraphs_retained"
        ],
        "selection_inventory_id": inventory["selection_inventory_id"],
        "selection_inventory_sha256": digest(inventory_content),
        "equation_review_status_counts": {
            "unreviewed": len(referenced_equations)
        },
        "accepted_equation_count": 0,
        "chunk_text_eligible_equation_count": 0,
        "recognized_equation_text_count": 0,
        "referenced_equation_rendered_bytes": selected_bytes,
        "referenced_figure_rendered_bytes": figure_bytes,
        "utf8_bytes": len(transcript),
        "output": "reading-transcript.jsonl",
        "limitations": [
            "automated_unreviewed",
            "equation_images_and_native_source_evidence_only",
            "historical_recognition_text_discarded",
            "equations_not_chunk_text_eligible",
            "auxiliary_and_rejected_equations_retained_outside_transcript",
            "legacy_figure_selection_preserved",
        ],
        "model_execution_performed": False,
        "search_indexing_performed": False,
        "publication_performed": False,
    }
    summary = {
        **summary_body,
        "reading_transcript_id": identity(
            "reference-legacy-reading-transcript", summary_body
        ),
    }
    summary_content = (
        json.dumps(
            summary, ensure_ascii=False, indent=2, sort_keys=True
        ).encode()
        + b"\n"
    )
    create_once(
        output_root / "reading-transcript-summary.json", summary_content
    )
    projection = validate_page_projection(
        PageProjectionPlanEntry(
            document_id=book.document_id,
            filename=book.filename,
            title=book.title,
            source_sha256=book.digest,
            expected_page_count=book.pages,
        ),
        source_path=REFERENCES / book.digest / "document.pdf",
        transcript_path=output_root / "reading-transcript.jsonl",
        summary_path=output_root / "reading-transcript-summary.json",
        baseline_path=BASELINES
        / book.digest[:2]
        / book.digest
        / "composed-transcript.json",
        media_root=output_root,
    )
    validation = page_projection_validation_report_bytes(projection.report)
    create_once(output_root / "reading-transcript-validation.json", validation)
    return {
        "document_id": book.document_id,
        "book": book.name,
        "selection_inventory_id": inventory["selection_inventory_id"],
        "selected_equation_count": len(referenced_equations),
        "retained_assembly_count": len(selection_records)
        - len(referenced_equations),
        "figure_count": len(referenced_figures),
        "reading_transcript_id": summary["reading_transcript_id"],
        "transcript_sha256": digest(transcript),
        "summary_sha256": digest(summary_content),
        "validation_id": projection.report.validation_id,
        "validation_sha256": digest(validation),
    }


def main() -> None:
    results = [recompose(book) for book in BOOKS]
    body = {
        "contract_version": "1.0",
        "status": "complete",
        "book_count": len(results),
        "page_count": sum(book.pages for book in BOOKS),
        "selected_equation_count": sum(
            result["selected_equation_count"] for result in results
        ),
        "recognized_equation_text_count": 0,
        "books": results,
        "model_execution_performed": False,
        "database_projection_performed": False,
        "search_indexing_performed": False,
        "publication_performed": False,
    }
    value = {
        **body,
        "collection_id": identity(
            "reference-legacy-reading-transcript-collection", body
        ),
    }
    content = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode()
        + b"\n"
    )
    status = create_once(OUTPUT / "summary-all.json", content)
    print(
        json.dumps(
            {
                "status": status,
                "collection_id": value["collection_id"],
                "collection_sha256": digest(content),
                "book_count": value["book_count"],
                "page_count": value["page_count"],
                "selected_equation_count": value["selected_equation_count"],
                "books": [
                    {
                        "book": item["book"],
                        "selected_equation_count": item[
                            "selected_equation_count"
                        ],
                        "validation_id": item["validation_id"],
                    }
                    for item in results
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    os.umask(0o077)
    main()
