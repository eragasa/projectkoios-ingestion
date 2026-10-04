#!/Users/eugene/repos/projectkoios-ingestion/.venv/bin/python
from __future__ import annotations

import importlib.util
import json
import os
from collections import Counter
from pathlib import Path

from projectkoios.ingestion import (
    CleanTranscriptRequest,
    DeterministicCleanTranscriptProjector,
)

ROOT = Path(
    "/Users/eugene/projects/projectkoios/artifacts/reference-multimodal-v1/Kittel8ed"
)
ENRICHED = ROOT / "enriched-transcript.json"
OUTPUT = ROOT / "reading-transcript.jsonl"
SUMMARY = ROOT / "reading-transcript-summary.json"
OPERATION = (
    Path(__file__).resolve().parent / "001.enrich_kittel8ed_multimodal.py"
)
EXPECTED_PAGES = 700
EXPECTED_FIGURES = 703
EXPECTED_PRIMARY_EQUATIONS = 6


def atomic_write(path: Path, content: bytes) -> None:
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def compact_text(value: str) -> str:
    return " ".join(value.split())


def load_operation():
    specification = importlib.util.spec_from_file_location(
        "kittel_operation", OPERATION
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("cannot load retained Kittel operation")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def overlaps_region(box: list[float], region_box: list[float]) -> bool:
    x0, y0, x1, y1 = box
    rx0, ry0, rx1, ry1 = region_box
    center_inside = (
        rx0 <= (x0 + x1) / 2.0 <= rx1 and ry0 <= (y0 + y1) / 2.0 <= ry1
    )
    intersection = max(0.0, min(x1, rx1) - max(x0, rx0)) * max(
        0.0, min(y1, ry1) - max(y0, ry0)
    )
    area = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    return center_inside or (area > 0.0 and intersection / area >= 0.5)


def candidate_geometry(candidate: dict[str, object]) -> list[float]:
    components = candidate["components"]
    if not isinstance(components, list) or not components:
        raise ValueError("figure candidate has no components")
    boxes = [component["source_bounding_box"] for component in components]
    return [
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    ]


def padded_captioned_figure_geometry(box: list[float]) -> list[float]:
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


def main() -> int:
    os.umask(0o077)
    operation = load_operation()
    original, _baseline = operation.check_inputs()
    enriched = json.loads(ENRICHED.read_text(encoding="utf-8"))
    if (
        enriched["page_count"] != EXPECTED_PAGES
        or len(enriched["pages"]) != EXPECTED_PAGES
    ):
        raise ValueError("enriched transcript does not cover 700 pages")

    pages: list[dict[str, object]] = []
    counts: Counter[str] = Counter()
    exclusion_reasons: Counter[str] = Counter()

    for chunk_number in range(1, 71):
        data = operation.load_chunk(original, chunk_number)
        layouts = data[2]
        transcription = data[-1]
        projector = DeterministicCleanTranscriptProjector()
        clean = projector.action(
            request=CleanTranscriptRequest.create(
                transcription_result=transcription,
                layouts=layouts,
                configuration=projector.configuration,
            )
        )
        clean_exclusions: dict[int, set[str]] = {}
        for exclusion in clean.exclusions:
            clean_exclusions.setdefault(exclusion.page_index, set()).add(
                exclusion.block_id
            )
            exclusion_reasons[exclusion.reason.value] += 1

        retained = json.loads(
            (
                ROOT
                / "chunks"
                / f"chunk-{chunk_number:03d}"
                / "structured-transcription.json"
            ).read_text(encoding="utf-8")
        )
        retained_items_by_page: dict[int, list[dict[str, object]]] = {}
        for item in retained["items"]:
            retained_items_by_page.setdefault(item["page_index"], []).append(
                item
            )

        for local_page in range(10):
            physical_page = (chunk_number - 1) * 10 + local_page + 1
            source_page = enriched["pages"][physical_page - 1]
            printed_page = source_page.get("printed_page_label")
            citation = {
                "physical_page": physical_page,
                "printed_page": printed_page,
            }

            figures_by_candidate: dict[str, dict[str, object]] = {}
            associated_block_ids: set[str] = set()
            association_geometry: list[list[float]] = []
            figure_geometry: list[tuple[list[float], list[float]]] = []
            for figure in source_page["figures"]:
                candidate = figure["owner_candidate"]
                candidate_id = candidate["candidate_id"]
                associations = [
                    {
                        "role": item["role"],
                        "text": compact_text(item["text"]),
                    }
                    for item in candidate["associations"]
                ]
                associated_block_ids.update(
                    item["block_id"] for item in candidate["associations"]
                )
                association_geometry.extend(
                    span["bounding_box"]
                    for item in candidate["associations"]
                    for span in item["source_spans"]
                    if span["bounding_box"] is not None
                )
                captions = [
                    item["text"]
                    for item in associations
                    if item["role"] == "caption"
                ]
                exact_figure_box = candidate_geometry(candidate)
                figure_geometry.append(
                    (
                        exact_figure_box,
                        padded_captioned_figure_geometry(exact_figure_box)
                        if captions
                        else exact_figure_box,
                    )
                )
                figures_by_candidate[candidate_id] = {
                    "type": "figure",
                    "png_path": figure["png_path"],
                    "caption": " ".join(captions) if captions else None,
                    "associations": associations,
                    "status": figure["caption_status"],
                }

            equations_by_candidate: dict[str, dict[str, object]] = {}
            accepted_equation_block_ids: set[str] = set()
            accepted_equation_geometry: list[list[float]] = []
            for equation in source_page["equations"]:
                record = equation["owner_index_record"]
                if record["tier"] != "primary" or not record["latex_proposal"]:
                    raise ValueError(
                        "default equation list contains a non-primary record"
                    )
                compact = {
                    "type": "equation",
                    "latex": record["latex_proposal"],
                    "mathml": record["mathml_proposal"],
                    "native_text": compact_text(
                        record["sanitized_native_text"]
                    ),
                    "png_path": equation["evidence_path"],
                    "status": "automated_unreviewed_primary_tier",
                    "accepted": False,
                    "chunk_text_eligible": False,
                    "review_required": True,
                }
                for candidate_id in record["candidate_ids"]:
                    equations_by_candidate[candidate_id] = compact
                accepted_equation_block_ids.update(record["source_block_ids"])
                accepted_equation_geometry.append(record["source_bounding_box"])

            emitted_figures: set[str] = set()
            emitted_equation_objects: set[int] = set()
            blocks: list[dict[str, object]] = []
            for item in sorted(
                retained_items_by_page.get(local_page, []),
                key=lambda value: value["order_index"],
            ):
                kind = item["item_kind"]
                if kind == "page_anchor":
                    continue
                if kind == "figure":
                    candidate_id = item["source_object_id"]
                    figure = figures_by_candidate.get(candidate_id)
                    if (
                        figure is not None
                        and candidate_id not in emitted_figures
                    ):
                        blocks.append(figure)
                        emitted_figures.add(candidate_id)
                    continue
                if kind == "equation":
                    equation = equations_by_candidate.get(
                        item["source_object_id"]
                    )
                    if (
                        equation is not None
                        and id(equation) not in emitted_equation_objects
                    ):
                        blocks.append(equation)
                        emitted_equation_objects.add(id(equation))
                    continue
                if kind not in {"prose", "heading"}:
                    continue
                text = item.get("normalized_text")
                if not isinstance(text, str) or not text.strip():
                    continue
                block_ids = set(item["source_block_ids"])
                if block_ids & clean_exclusions.get(local_page, set()):
                    counts["paragraphs_excluded_by_clean_projection"] += 1
                    continue
                if block_ids & associated_block_ids:
                    counts["figure_association_fragments_suppressed"] += 1
                    continue
                if any(
                    overlaps_region(span["bounding_box"], association_box)
                    for span in item["source_spans"]
                    if span["bounding_box"] is not None
                    for association_box in association_geometry
                ):
                    counts[
                        "figure_association_geometry_fragments_suppressed"
                    ] += 1
                    continue
                if block_ids & accepted_equation_block_ids or any(
                    overlaps_region(span["bounding_box"], equation_box)
                    for span in item["source_spans"]
                    if span["bounding_box"] is not None
                    for equation_box in accepted_equation_geometry
                ):
                    counts["primary_equation_fragments_suppressed"] += 1
                    continue
                exact_figure_overlap = any(
                    overlaps_region(span["bounding_box"], exact_box)
                    for span in item["source_spans"]
                    if span["bounding_box"] is not None
                    for exact_box, _padded_box in figure_geometry
                )
                padded_figure_overlap = any(
                    overlaps_region(span["bounding_box"], padded_box)
                    for span in item["source_spans"]
                    if span["bounding_box"] is not None
                    for _exact_box, padded_box in figure_geometry
                )
                if exact_figure_overlap or padded_figure_overlap:
                    counts["figure_region_text_fragments_suppressed"] += 1
                    if not exact_figure_overlap:
                        counts[
                            "captioned_figure_padding_fragments_suppressed"
                        ] += 1
                    continue
                if printed_page is not None and compact_text(
                    text
                ) == compact_text(str(printed_page)):
                    counts["printed_page_label_fragments_suppressed"] += 1
                    continue
                block: dict[str, object] = {
                    "type": "paragraph",
                    "text": text,
                }
                if kind == "heading":
                    block["style"] = "heading"
                    counts["headings"] += 1
                blocks.append(block)
                counts["paragraphs"] += 1

            for candidate_id, figure in figures_by_candidate.items():
                if candidate_id not in emitted_figures:
                    blocks.append(figure)
                    emitted_figures.add(candidate_id)
                    counts["geometry_fallback_figures"] += 1
            unique_equations = {
                id(value): value for value in equations_by_candidate.values()
            }
            for identity, equation in unique_equations.items():
                if identity not in emitted_equation_objects:
                    blocks.append(equation)
                    emitted_equation_objects.add(identity)
                    counts["geometry_fallback_equations"] += 1

            for order, block in enumerate(blocks):
                block["order"] = order
            counts["figures"] += len(emitted_figures)
            counts["primary_equations"] += len(emitted_equation_objects)
            counts["pages"] += 1
            pages.append(
                {
                    "physical_page": physical_page,
                    "printed_page": printed_page,
                    "citation": citation,
                    "blocks": blocks,
                }
            )

    if len(pages) != EXPECTED_PAGES:
        raise ValueError("reading transcript page count is incomplete")
    if [page["physical_page"] for page in pages] != list(
        range(1, EXPECTED_PAGES + 1)
    ):
        raise ValueError("reading transcript pages are out of order")
    if counts["figures"] != EXPECTED_FIGURES:
        raise ValueError("reading transcript figure coverage is incomplete")
    if counts["primary_equations"] != EXPECTED_PRIMARY_EQUATIONS:
        raise ValueError(
            "reading transcript primary equation coverage is incomplete"
        )

    lines = []
    for page in pages:
        for expected_order, block in enumerate(page["blocks"]):
            if block["order"] != expected_order:
                raise ValueError("page block order is not contiguous")
            png_path = block.get("png_path")
            if png_path is not None:
                resolved = ROOT / png_path
                if (
                    not resolved.is_file()
                    or not resolved.read_bytes().startswith(
                        b"\x89PNG\r\n\x1a\n"
                    )
                ):
                    raise ValueError(
                        f"referenced PNG is missing or invalid: {png_path}"
                    )
        lines.append(
            json.dumps(page, ensure_ascii=False, separators=(",", ":"))
        )
    content = ("\n".join(lines) + "\n").encode("utf-8")
    if (
        b":sha256:" in content
        or b'"owner_' in content
        or b'"source_' in content
    ):
        raise ValueError(
            "compact transcript leaked owner identities or payload fields"
        )
    atomic_write(OUTPUT, content)

    summary = {
        "status": "complete",
        "pages": counts["pages"],
        "paragraphs": counts["paragraphs"],
        "headings": counts["headings"],
        "primary_equations": counts["primary_equations"],
        "figures": counts["figures"],
        "clean_projection_exclusions": dict(sorted(exclusion_reasons.items())),
        "paragraphs_excluded_by_clean_projection": counts[
            "paragraphs_excluded_by_clean_projection"
        ],
        "figure_association_fragments_suppressed": counts[
            "figure_association_fragments_suppressed"
        ],
        "figure_association_geometry_fragments_suppressed": counts[
            "figure_association_geometry_fragments_suppressed"
        ],
        "primary_equation_fragments_suppressed": counts[
            "primary_equation_fragments_suppressed"
        ],
        "printed_page_label_fragments_suppressed": counts[
            "printed_page_label_fragments_suppressed"
        ],
        "figure_region_text_fragments_suppressed": counts[
            "figure_region_text_fragments_suppressed"
        ],
        "captioned_figure_padding_fragments_suppressed": counts[
            "captioned_figure_padding_fragments_suppressed"
        ],
        "geometry_fallback_figures": counts["geometry_fallback_figures"],
        "geometry_fallback_equations": counts["geometry_fallback_equations"],
        "utf8_bytes": len(content),
        "output": "reading-transcript.jsonl",
        "limitations": [
            "automated_unreviewed",
            "primary_equations_only",
            "primary_equations_are_evidence_only_and_excluded_from_chunk_text_until_reviewed",
            "auxiliary_and_rejected_equations_omitted",
            "figure_descriptions_not_invented",
        ],
    }
    atomic_write(
        SUMMARY,
        (
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n"
        ).encode("utf-8"),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
