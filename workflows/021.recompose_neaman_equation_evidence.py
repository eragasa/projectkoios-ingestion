#!/Users/eugene/repos/projectkoios-ingestion/.venv/bin/python
from __future__ import annotations

import hashlib
import json
import os
import stat
from collections import Counter
from pathlib import Path

import pymupdf
from projectkoios.ingestion.page_projection import (
    PageProjectionPlanEntry,
    page_projection_validation_report_bytes,
    validate_page_projection,
)

LEGACY = Path(
    "/Users/eugene/projects/projectkoios/artifacts/reference-multimodal-v1/Neaman3Ed"
)
REFERENCES = Path("/Users/eugene/projects/projectkoios/references")
BASELINES = Path(
    "/Users/eugene/projects/projectkoios/artifacts/reference-page-resolution-v1/objects"
)
OUTPUT = Path(
    "/Users/eugene/projects/projectkoios/artifacts/reference-neaman-reading-transcript-v2"
)
SOURCE_SHA256 = (
    "31dce1ae5f09199951a496da12d00f7873f0ccbce00f3cd67449438b187d3761"
)
PAGES = 566
CHUNKS = 114
CHUNK_PAGES = 5
PNG = b"\x89PNG\r\n\x1a\n"


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


def json_once(path: Path, value: object) -> tuple[str, str, int]:
    content = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode()
        + b"\n"
    )
    return create_once(path, content), digest(content), len(content)


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


def padded(box: list[float]) -> list[float]:
    width = box[2] - box[0]
    height = box[3] - box[1]
    x_padding = min(48.0, max(6.0, width * 0.15))
    y_padding = min(48.0, max(6.0, height * 0.15))
    return [
        max(0.0, box[0] - x_padding),
        max(0.0, box[1] - y_padding),
        box[2] + x_padding,
        box[3] + y_padding,
    ]


def main() -> None:
    source_path = REFERENCES / SOURCE_SHA256 / "document.pdf"
    source = exact(source_path)
    if digest(source) != SOURCE_SHA256:
        raise RuntimeError("Neaman source digest differs")
    baseline_path = (
        BASELINES
        / SOURCE_SHA256[:2]
        / SOURCE_SHA256
        / "composed-transcript.json"
    )
    baseline_bytes = exact(baseline_path)
    baseline = json.loads(baseline_bytes)
    if baseline["page_count"] != PAGES or len(baseline["pages"]) != PAGES:
        raise RuntimeError("Neaman baseline coverage differs")

    document = pymupdf.open(stream=source, filetype="pdf")
    try:
        if document.page_count != PAGES:
            raise RuntimeError("Neaman PDF page coverage differs")
        page_dimensions = tuple(
            (float(page.cropbox.width), float(page.cropbox.height))
            for page in document
        )
    finally:
        document.close()

    chunk_values: dict[int, dict[str, object]] = {}
    selection_records = []
    source_bindings = []
    disposition_counts: Counter[str] = Counter()
    historical_status_counts: Counter[str] = Counter()
    tier_counts: Counter[str] = Counter()
    selected_candidate_memberships = 0
    all_candidate_memberships = 0
    selected_ids: set[str] = set()
    selected_rendered_bytes = 0
    all_rendered_bytes = 0
    for chunk in range(1, CHUNKS + 1):
        root = LEGACY / "chunks" / f"chunk-{chunk:03d}"
        projection_bytes = exact(root / "projection.json")
        projection = json.loads(projection_bytes)
        enrichment = root / "equation-enrichment"
        index_path = enrichment / "index.json"
        recognition_path = enrichment / "recognition.json"
        assemblies_path = enrichment / "assemblies.json"
        if index_path.is_file():
            index_bytes = exact(index_path)
            recognition_bytes = exact(recognition_path)
            assemblies_bytes = exact(assemblies_path)
            index = json.loads(index_bytes)
            recognition = json.loads(recognition_bytes)
            assemblies = json.loads(assemblies_bytes)["assemblies"]
            records = index["records"]
            if len(records) != len(assemblies):
                raise RuntimeError(
                    f"chunk {chunk}: assembly/index coverage differs"
                )
            proposals = {
                item["assembly_id"]: item for item in recognition["proposals"]
            }
            if len(proposals) != len(records):
                raise RuntimeError(
                    f"chunk {chunk}: recognition/index coverage differs"
                )
            source_bindings.append(
                {
                    "chunk_number": chunk,
                    "projection_sha256": digest(projection_bytes),
                    "index_sha256": digest(index_bytes),
                    "recognition_sha256": digest(recognition_bytes),
                    "assemblies_sha256": digest(assemblies_bytes),
                }
            )
            equation_records = []
            for ordinal, (record, assembly) in enumerate(
                zip(records, assemblies, strict=True), 1
            ):
                if (
                    record["assembly_id"] != assembly["assembly_id"]
                    or assembly["ordinal"] != ordinal
                ):
                    raise RuntimeError(f"chunk {chunk}: assembly order differs")
                proposal = proposals[record["assembly_id"]]
                status = proposal["status"]
                tier = record["tier"]
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
                image_source = enrichment / f"assembly-{ordinal:03d}.png"
                image = exact(image_source)
                if (
                    not image.startswith(PNG)
                    or digest(image) != record["rendered_region_sha256"]
                ):
                    raise RuntimeError(
                        f"chunk {chunk} assembly {ordinal}: rendered evidence differs"
                    )
                all_rendered_bytes += len(image)
                all_candidate_memberships += len(record["candidate_ids"])
                tier_counts[tier] += 1
                historical_status_counts[status] += 1
                disposition_counts[disposition] += 1
                output_path = None
                if selected:
                    output_path = f"evidence/equations/chunk-{chunk:03d}/assembly-{ordinal:03d}.png"
                    create_once(OUTPUT / output_path, image)
                    selected_ids.add(record["assembly_id"])
                    selected_rendered_bytes += len(image)
                    selected_candidate_memberships += len(
                        record["candidate_ids"]
                    )
                global_page_index = (chunk - 1) * CHUNK_PAGES + int(
                    record["page_index"]
                )
                item = {
                    "assembly_id": record["assembly_id"],
                    "chunk_number": chunk,
                    "ordinal": ordinal,
                    "page_index": global_page_index,
                    "candidate_ids": record["candidate_ids"],
                    "source_block_ids": record["source_block_ids"],
                    "source_bounding_box": record["source_bounding_box"],
                    "rendered_source_sha256": digest(image),
                    "rendered_bytes": len(image),
                    "historical_index_tier": tier,
                    "historical_recognition_status": status,
                    "transcript_disposition": disposition,
                    "transcript_rendered_member": output_path,
                    "recognition_status": "deferred_processor_unsuitable"
                    if selected
                    else "not_requested",
                    "review_status": "unreviewed",
                    "accepted": False,
                    "review_required": True,
                    "chunk_text_eligible": False,
                    "recognized_text_retained": False,
                }
                selection_records.append(item)
                equation_records.append((record, item))
            chunk_values[chunk] = {
                "projection": projection,
                "equations": equation_records,
                "root": root,
            }
        else:
            source_bindings.append(
                {
                    "chunk_number": chunk,
                    "projection_sha256": digest(projection_bytes),
                    "index_sha256": None,
                    "recognition_sha256": None,
                    "assemblies_sha256": None,
                }
            )
            chunk_values[chunk] = {
                "projection": projection,
                "equations": [],
                "root": root,
            }

    if len(selection_records) != 1229 or all_candidate_memberships != 1821:
        raise RuntimeError("Neaman retained assembly coverage differs")
    if disposition_counts != {
        "selected_primary_equation_evidence": 457,
        "retained_auxiliary_evidence": 771,
        "retained_rejected_evidence": 1,
    }:
        raise RuntimeError("Neaman equation selection differs")
    if historical_status_counts != {
        "proposed": 436,
        "failed": 21,
        "not_requested": 772,
    }:
        raise RuntimeError("Neaman historical recognition counts differ")

    selection_body = {
        "contract_version": "1.0",
        "book": "Neaman3Ed",
        "document_id": "doc-06",
        "source_sha256": SOURCE_SHA256,
        "selection_policy": "recognition-independent-retention-of-every-vendor-neutral-primary-evidence-assembly",
        "source_binding_sha256": digest(canonical(source_bindings)),
        "assembly_count": len(selection_records),
        "candidate_membership_count": all_candidate_memberships,
        "selected_candidate_membership_count": selected_candidate_memberships,
        "historical_index_tier_counts": dict(sorted(tier_counts.items())),
        "historical_recognition_status_counts": dict(
            sorted(historical_status_counts.items())
        ),
        "disposition_counts": dict(sorted(disposition_counts.items())),
        "all_rendered_bytes": all_rendered_bytes,
        "selected_rendered_bytes": selected_rendered_bytes,
        "records": selection_records,
        "recognized_text_retained_count": 0,
        "accepted_count": 0,
        "review_status_counts": {"unreviewed": len(selection_records)},
        "review_required_count": len(selection_records),
        "chunk_text_eligible_count": 0,
        "model_execution_performed": False,
    }
    selection = {
        **selection_body,
        "selection_inventory_id": identity(
            "reference-neaman-equation-evidence-selection", selection_body
        ),
    }
    selection_status, selection_sha256, selection_size = json_once(
        OUTPUT / "equation-evidence-selection.json", selection
    )

    counts: Counter[str] = Counter()
    historical_selected_counts: Counter[str] = Counter()
    lines = []
    referenced_equations: set[str] = set()
    referenced_figures: set[str] = set()
    figure_source_bytes = 0
    figure_rendered_bytes = 0
    for chunk in range(1, CHUNKS + 1):
        offset = (chunk - 1) * CHUNK_PAGES
        values = chunk_values[chunk]
        projection = values["projection"]
        root = values["root"]
        items_by_page: dict[int, list[dict[str, object]]] = {}
        for item in projection["items"]:
            items_by_page.setdefault(int(item["page_index"]), []).append(item)
        exclusions: dict[int, set[str]] = {}
        for item in projection["clean_exclusions"]:
            exclusions.setdefault(int(item["page_index"]), set()).add(
                item["block_id"]
            )
            counts["clean_exclusions"] += 1
        equations_by_page: dict[
            int, list[tuple[dict[str, object], dict[str, object]]]
        ] = {}
        for record, selected in values["equations"]:
            if (
                selected["transcript_disposition"]
                == "selected_primary_equation_evidence"
            ):
                equations_by_page.setdefault(
                    int(record["page_index"]), []
                ).append((record, selected))
        figure_metadata_by_page: dict[
            int, list[tuple[Path, dict[str, object]]]
        ] = {}
        for metadata_path in sorted(
            root.glob("figures/figure-*/metadata.json")
        ):
            metadata_bytes = exact(metadata_path)
            metadata = json.loads(metadata_bytes)
            figure_metadata_by_page.setdefault(
                int(metadata["source_page"]), []
            ).append((metadata_path, metadata))
            figure_source_bytes += len(metadata_bytes)
        for local in range(min(CHUNK_PAGES, PAGES - offset)):
            physical = offset + local + 1
            base = baseline["pages"][physical - 1]
            printed = base.get("printed_page_label")
            figures: dict[str, dict[str, object]] = {}
            association_ids: set[str] = set()
            association_boxes: list[list[float]] = []
            figure_boxes: list[tuple[list[float], list[float]]] = []
            used_caption_ids: set[str] = set()
            page_width, page_height = page_dimensions[physical - 1]
            page_area = page_width * page_height
            for metadata_path, metadata in figure_metadata_by_page.get(
                physical, []
            ):
                counts["figure_evidence_total"] += 1
                caption_records = [
                    item
                    for item in metadata["associations"]
                    if item["role"] == "caption"
                ]
                if not caption_records:
                    counts["figure_evidence_omitted_unassociated"] += 1
                    continue
                exact_box = metadata["visual_box"]
                width = exact_box[2] - exact_box[0]
                height = exact_box[3] - exact_box[1]
                area_fraction = (
                    width * height / page_area if page_area > 0 else 1.0
                )
                if area_fraction >= 0.80:
                    counts["figure_evidence_omitted_page_background"] += 1
                    continue
                if area_fraction < 0.005 or min(width, height) < 24.0:
                    counts["figure_evidence_omitted_non_reading_scale"] += 1
                    continue
                caption_ids = tuple(
                    item["block_id"] for item in caption_records
                )
                if any(value in used_caption_ids for value in caption_ids):
                    counts["figure_evidence_omitted_duplicate_caption"] += 1
                    continue
                used_caption_ids.update(caption_ids)
                associations = [
                    {"role": item["role"], "text": compact(item["text"])}
                    for item in metadata["associations"]
                ]
                association_ids.update(
                    item["block_id"] for item in metadata["associations"]
                )
                association_boxes.extend(
                    span["bounding_box"]
                    for item in metadata["associations"]
                    for span in item["source_spans"]
                    if span["bounding_box"] is not None
                )
                captions = [
                    item["text"]
                    for item in associations
                    if item["role"] == "caption"
                ]
                figure_boxes.append((exact_box, padded(exact_box)))
                ordinal = metadata_path.parent.name.removeprefix("figure-")
                source_image = metadata_path.parent / "candidate.png"
                image = exact(source_image)
                if not image.startswith(PNG):
                    raise RuntimeError(
                        f"invalid figure evidence: {source_image}"
                    )
                output_path = (
                    f"evidence/figures/chunk-{chunk:03d}/figure-{ordinal}.png"
                )
                create_once(OUTPUT / output_path, image)
                figure_rendered_bytes += len(image)
                figures[metadata["candidate_id"]] = {
                    "type": "figure",
                    "candidate_id": metadata["candidate_id"],
                    "png_path": output_path,
                    "png_sha256": digest(image),
                    "caption": " ".join(captions),
                    "associations": associations,
                    "status": "associated_unreviewed",
                }
            equations: dict[str, dict[str, object]] = {}
            equation_block_ids: set[str] = set()
            equation_boxes: list[list[float]] = []
            for record, selected in equations_by_page.get(local, []):
                block = {
                    "type": "equation",
                    "assembly_id": record["assembly_id"],
                    "candidate_ids": record["candidate_ids"],
                    "latex": None,
                    "mathml": None,
                    "native_text": compact(record["sanitized_native_text"]),
                    "png_path": selected["transcript_rendered_member"],
                    "png_sha256": selected["rendered_source_sha256"],
                    "status": "recognition_deferred_processor_unsuitable",
                    "historical_recognition_status": selected[
                        "historical_recognition_status"
                    ],
                    "review_status": "unreviewed",
                    "accepted": False,
                    "review_required": True,
                    "chunk_text_eligible": False,
                }
                for candidate_id in record["candidate_ids"]:
                    equations[candidate_id] = block
                equation_block_ids.update(record["source_block_ids"])
                equation_boxes.append(record["source_bounding_box"])
            blocks = []
            emitted_figures: set[str] = set()
            emitted_equations: set[int] = set()
            for item in sorted(
                items_by_page.get(local, []),
                key=lambda value: int(value["order_index"]),
            ):
                kind = item["item_kind"]
                if kind == "page_anchor":
                    continue
                if kind == "figure":
                    figure = figures.get(item["source_object_id"])
                    if (
                        figure is not None
                        and item["source_object_id"] not in emitted_figures
                    ):
                        blocks.append(figure)
                        emitted_figures.add(item["source_object_id"])
                    continue
                if kind == "equation":
                    equation = equations.get(item["source_object_id"])
                    if (
                        equation is not None
                        and id(equation) not in emitted_equations
                    ):
                        blocks.append(equation)
                        emitted_equations.add(id(equation))
                    continue
                if (
                    kind not in ("prose", "heading")
                    or not item["normalized_text"]
                ):
                    continue
                source_ids = set(item["source_block_ids"])
                spans = [
                    span["bounding_box"]
                    for span in item["source_spans"]
                    if span["bounding_box"] is not None
                ]
                if source_ids & exclusions.get(local, set()):
                    continue
                if source_ids & association_ids:
                    continue
                if any(
                    overlaps(box, association)
                    for box in spans
                    for association in association_boxes
                ):
                    counts["association_geometry_suppressed"] += 1
                    continue
                if source_ids & equation_block_ids or any(
                    overlaps(box, equation_box)
                    for box in spans
                    for equation_box in equation_boxes
                ):
                    counts["equation_geometry_suppressed"] += 1
                    continue
                exact_hit = any(
                    overlaps(box, exact_box)
                    for box in spans
                    for exact_box, _ in figure_boxes
                )
                padded_hit = any(
                    overlaps(box, padding)
                    for box in spans
                    for _, padding in figure_boxes
                )
                if exact_hit or padded_hit:
                    counts["figure_region_suppressed"] += 1
                    if not exact_hit:
                        counts["caption_padding_suppressed"] += 1
                    continue
                text = item["normalized_text"]
                if printed is not None and compact(text) == compact(
                    str(printed)
                ):
                    counts["page_labels_suppressed"] += 1
                    continue
                paragraph = {"type": "paragraph", "text": text}
                if kind == "heading":
                    paragraph["style"] = "heading"
                    counts["headings"] += 1
                blocks.append(paragraph)
                counts["paragraphs"] += 1
            for candidate_id, figure in figures.items():
                if candidate_id not in emitted_figures:
                    blocks.append(figure)
                    emitted_figures.add(candidate_id)
            for equation_key, equation in {
                id(value): value for value in equations.values()
            }.items():
                if equation_key not in emitted_equations:
                    blocks.append(equation)
                    emitted_equations.add(equation_key)
            for order, block in enumerate(blocks):
                block["order"] = order
                if block["type"] == "equation":
                    assembly_id = block["assembly_id"]
                    if assembly_id in referenced_equations:
                        raise RuntimeError("equation assembly projected twice")
                    referenced_equations.add(assembly_id)
                    historical_selected_counts[
                        block["historical_recognition_status"]
                    ] += 1
                elif block["type"] == "figure":
                    candidate_id = block["candidate_id"]
                    if candidate_id in referenced_figures:
                        raise RuntimeError("figure evidence projected twice")
                    referenced_figures.add(candidate_id)
            counts["figures"] += len(emitted_figures)
            counts["primary_equations"] += len(emitted_equations)
            page = {
                "physical_page": physical,
                "printed_page": printed,
                "citation": {
                    "physical_page": physical,
                    "printed_page": printed,
                },
                "blocks": blocks,
            }
            paragraph_values = [
                block["text"]
                for block in blocks
                if block["type"] == "paragraph"
            ]
            normalized_paragraphs = {
                compact(value) for value in paragraph_values
            }
            for block in blocks:
                if (
                    block["type"] == "figure"
                    and block["caption"]
                    and compact(block["caption"]) in normalized_paragraphs
                ):
                    raise RuntimeError(
                        f"figure caption duplicated on page {physical}"
                    )
                if block["type"] == "equation":
                    if (
                        block["latex"] is not None
                        or block["mathml"] is not None
                    ):
                        raise RuntimeError(
                            "generated recognition text entered transcript"
                        )
                    if (
                        block["native_text"]
                        and compact(block["native_text"])
                        in normalized_paragraphs
                    ):
                        raise RuntimeError(
                            f"equation source duplicated on page {physical}"
                        )
            lines.append(canonical(page))

    if referenced_equations != selected_ids or len(referenced_figures) != 79:
        raise RuntimeError("Neaman transcript visual coverage differs")
    if counts["primary_equations"] != 457 or historical_selected_counts != {
        "proposed": 436,
        "failed": 21,
    }:
        raise RuntimeError("Neaman transcript equation counts differ")
    transcript = b"\n".join(lines) + b"\n"
    transcript_status = create_once(
        OUTPUT / "reading-transcript.jsonl", transcript
    )
    summary_body = {
        "contract_version": "2.0",
        "status": "complete",
        "book": "Neaman3Ed",
        "document_id": "doc-06",
        "source_sha256": SOURCE_SHA256,
        "pages": PAGES,
        **dict(sorted(counts.items())),
        "equation_evidence_selection_inventory_id": selection[
            "selection_inventory_id"
        ],
        "equation_evidence_selection_inventory_sha256": selection_sha256,
        "historical_selected_recognition_status_counts": dict(
            sorted(historical_selected_counts.items())
        ),
        "equation_review_status_counts": {
            "unreviewed": len(referenced_equations)
        },
        "accepted_equation_count": 0,
        "chunk_text_eligible_equation_count": 0,
        "recognized_equation_text_count": 0,
        "referenced_equation_rendered_bytes": selected_rendered_bytes,
        "referenced_figure_rendered_bytes": figure_rendered_bytes,
        "utf8_bytes": len(transcript),
        "output": "reading-transcript.jsonl",
        "limitations": [
            "automated_unreviewed",
            "equation_images_and_native_source_evidence_only",
            "historical_recognition_text_discarded",
            "equations_not_chunk_text_eligible",
            "auxiliary_and_rejected_equations_retained_outside_transcript",
            "no_invented_figure_descriptions",
        ],
        "model_execution_performed": False,
        "search_indexing_performed": False,
        "publication_performed": False,
    }
    summary = {
        **summary_body,
        "reading_transcript_id": identity(
            "reference-neaman-reading-transcript", summary_body
        ),
    }
    summary_status, summary_sha256, summary_size = json_once(
        OUTPUT / "reading-transcript-summary.json", summary
    )

    plan = PageProjectionPlanEntry(
        document_id="doc-06",
        filename="Neaman3Ed.pdf",
        title="Semiconductor Physics and Devices",
        source_sha256=SOURCE_SHA256,
        expected_page_count=PAGES,
    )
    projection = validate_page_projection(
        plan,
        source_path=source_path,
        transcript_path=OUTPUT / "reading-transcript.jsonl",
        summary_path=OUTPUT / "reading-transcript-summary.json",
        baseline_path=baseline_path,
        media_root=OUTPUT,
    )
    validation = page_projection_validation_report_bytes(projection.report)
    validation_status = create_once(
        OUTPUT / "reading-transcript-validation.json", validation
    )
    validation_sha256 = digest(validation)
    closure_body = {
        "contract_version": "1.0",
        "status": "resolved_complete",
        "document_id": "doc-06",
        "book": "Neaman3Ed",
        "stale_control_state": {"stage": "projection", "state": "running"},
        "stale_control_state_reason": "a later replay reset the mutable checkpoint after three recorded completion events and stopped before restoring completion",
        "active_worker_found": False,
        "legacy_transcript_sha256": digest(
            exact(LEGACY / "reading-transcript.jsonl")
        ),
        "legacy_validation_id": json.loads(
            exact(LEGACY / "reading-transcript-validation.json")
        )["validation_id"],
        "authoritative_reading_transcript_id": summary["reading_transcript_id"],
        "authoritative_transcript_sha256": digest(transcript),
        "authoritative_validation_id": projection.report.validation_id,
        "authoritative_validation_sha256": validation_sha256,
        "equation_evidence_count": len(referenced_equations),
        "recognized_equation_text_count": 0,
        "model_execution_performed": False,
        "mutable_database_modified": False,
        "legacy_progress_modified": False,
    }
    closure = {
        **closure_body,
        "status_resolution_id": identity(
            "reference-neaman-status-resolution", closure_body
        ),
    }
    closure_status, closure_sha256, closure_size = json_once(
        OUTPUT / "status-resolution.json", closure
    )
    print(
        json.dumps(
            {
                "selection_status": selection_status,
                "selection_inventory_id": selection["selection_inventory_id"],
                "selection_sha256": selection_sha256,
                "selection_bytes": selection_size,
                "selected_equation_count": len(referenced_equations),
                "retained_auxiliary_count": disposition_counts[
                    "retained_auxiliary_evidence"
                ],
                "retained_rejected_count": disposition_counts[
                    "retained_rejected_evidence"
                ],
                "transcript_status": transcript_status,
                "reading_transcript_id": summary["reading_transcript_id"],
                "transcript_sha256": digest(transcript),
                "transcript_bytes": len(transcript),
                "summary_status": summary_status,
                "summary_sha256": summary_sha256,
                "summary_bytes": summary_size,
                "validation_status": validation_status,
                "validation_id": projection.report.validation_id,
                "validation_sha256": validation_sha256,
                "status_resolution_status": closure_status,
                "status_resolution_id": closure["status_resolution_id"],
                "status_resolution_sha256": closure_sha256,
                "status_resolution_bytes": closure_size,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    os.umask(0o077)
    main()
