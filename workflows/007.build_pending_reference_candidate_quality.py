#!/Users/eugene/repos/projectkoios-ingestion/.venv/bin/python
from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import replace
from io import BytesIO
from pathlib import Path

import pymupdf
from projectkoios.ingestion import (
    DeterministicEquationAssembler,
    DeterministicEquationCandidateDetector,
    DeterministicFigureCandidateDetector,
    DeterministicLayoutProcessor,
    DeterministicTableCandidateDetector,
    EquationAssemblyKind,
    EquationEvidenceStatus,
    FigureDetectionConfiguration,
    LayoutConfiguration,
    PyMuPdfExtractor,
    SourceDocument,
    TableDetectionConfiguration,
)
from projectkoios.ingestion.pdf.adapters.pymupdf.rendering import (
    PyMuPdfRegionRenderer,
)

ROOT = Path(
    "/Users/eugene/projects/projectkoios/artifacts/reference-multimodal-preparation-v2"
)
REFERENCE_ROOT = Path("/Users/eugene/projects/projectkoios/references")
PLAN_PATH = ROOT / "plan.json"


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


def json_once(path: Path, value: object) -> str:
    return create_once(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode()
        + b"\n",
    )


def chunk_pdf(source: bytes, first: int, last: int) -> bytes:
    original = pymupdf.open(stream=source, filetype="pdf")
    derived = pymupdf.open()
    try:
        derived.insert_pdf(original, from_page=first, to_page=last - 1)
        return derived.tobytes(garbage=4, deflate=True, no_new_id=True)
    finally:
        derived.close()
        original.close()


def spans(values: object, offset: int) -> list[dict[str, object]]:
    return [
        {
            "page_index": offset + span.page_index,
            "bounding_box": list(span.bounding_box)
            if span.bounding_box is not None
            else None,
        }
        for span in values
    ]


def context(value: object | None, offset: int) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "context_id": value.context_id,
        "direction": value.direction.value,
        "block_id": value.block_id,
        "source_spans": spans(value.source_spans, offset),
    }


def analyze(
    book: dict[str, object], chunk: dict[str, object], source_bytes: bytes
):
    name = str(book["book"])
    first = int(chunk["first_page_index"])
    last = int(chunk["last_page_index_exclusive"])
    content = chunk_pdf(source_bytes, first, last)
    source = SourceDocument.from_bytes(
        content,
        source_id=f"private:{name}:pages:{first + 1:04d}-{last:04d}",
        media_type="application/pdf",
        locator=f"private://{name}/pages-{first + 1:04d}-{last:04d}.pdf",
    )
    extraction = PyMuPdfExtractor(maximum_pages=last - first).extract(
        source, BytesIO(content)
    )
    filtered = []
    for page in extraction.document.pages:
        blocks = tuple(
            block
            for block in page.blocks
            if block.kind != "text"
            or all(
                span.bounding_box is None
                or (
                    0.0
                    <= span.bounding_box[0]
                    <= span.bounding_box[2]
                    <= page.width
                    and 0.0
                    <= span.bounding_box[1]
                    <= span.bounding_box[3]
                    <= page.height
                )
                for span in block.source_spans
            )
        )
        filtered.append(replace(page, blocks=blocks))
    document = replace(extraction.document, pages=tuple(filtered))
    layouts = DeterministicLayoutProcessor(
        LayoutConfiguration(max_raw_blocks_per_page=2_048)
    ).analyze(document)
    equation_renderer = PyMuPdfRegionRenderer(
        max_total_pixels=25_000_000, max_total_raster_bytes=100_000_000
    )
    broad_renderer = PyMuPdfRegionRenderer(
        max_total_pixels=100_000_000, max_total_raster_bytes=100_000_000
    )
    equations = DeterministicEquationCandidateDetector(
        region_renderer=equation_renderer
    ).detect_with_layout(document, BytesIO(content), layouts)
    figures = DeterministicFigureCandidateDetector(
        FigureDetectionConfiguration(
            minimum_embedded_dimension_points=12.0,
            minimum_embedded_area_points=576.0,
        ),
        region_renderer=broad_renderer,
    ).detect_with_layout(document, BytesIO(content), layouts)
    tables = DeterministicTableCandidateDetector(
        TableDetectionConfiguration(), region_renderer=broad_renderer
    ).detect_with_layout(document, BytesIO(content), layouts)
    assemblies = DeterministicEquationAssembler(
        renderer=equation_renderer
    ).assemble(equations, content)
    return equations, figures, tables, assemblies


def process(
    book: dict[str, object], chunk: dict[str, object], source_bytes: bytes
) -> dict[str, object]:
    name = str(book["book"])
    number = int(chunk["chunk_number"])
    offset = int(chunk["first_page_index"])
    directory = ROOT / "books" / name / "chunks" / f"chunk-{number:03d}"
    path = directory / "quality-inventory.json"
    if path.exists():
        value = json.loads(exact(path))
        for member in value["primary_recognition_members"]:
            payload = exact(directory / member["path"])
            if (
                len(payload) != member["bytes"]
                or digest(payload) != member["sha256"]
            ):
                raise RuntimeError(
                    f"{name} chunk {number}: primary member differs"
                )
        return value
    evidence_inventory = json.loads(exact(directory / "inventory.json"))
    equations, figures, tables, assemblies = analyze(book, chunk, source_bytes)
    if (
        equations.result_id
        != evidence_inventory["equation_detection_result_id"]
        or figures.result_id != evidence_inventory["figure_detection_result_id"]
        or tables.result_id != evidence_inventory["table_detection_result_id"]
    ):
        raise RuntimeError(
            f"{name} chunk {number}: replayed detection identity differs"
        )
    member_paths: dict[str, list[str]] = {}
    for member in evidence_inventory["members"]:
        member_paths.setdefault(member["candidate_id"], []).append(
            member["path"]
        )
    equation_records = [
        {
            "candidate_id": item.candidate_id,
            "kind": item.kind.value,
            "evidence_status": item.evidence_status.value,
            "confidence": item.confidence,
            "source_block_id": item.source_block_id,
            "source_label": item.source_label,
            "raw_text": item.raw_text,
            "source_spans": spans(item.source_spans, offset),
            "preceding_context": context(item.preceding_context, offset),
            "following_context": context(item.following_context, offset),
            "warning_ids": list(item.warning_ids),
            "rendered_members": member_paths[item.candidate_id],
        }
        for item in equations.candidates
    ]
    figure_records = [
        {
            "candidate_id": item.candidate_id,
            "evidence_status": item.evidence_status.value,
            "confidence": item.confidence,
            "source_label": item.source_label,
            "source_spans": spans(item.source_spans, offset),
            "components": [
                {
                    "component_id": component.component_id,
                    "component_index": component.component_index,
                    "artifact_kind": component.artifact_kind.value,
                    "source_bounding_box": list(component.source_bounding_box),
                }
                for component in item.components
            ],
            "associations": [
                {
                    "association_id": association.association_id,
                    "role": association.role.value,
                    "block_id": association.block_id,
                    "text": association.text,
                    "source_spans": spans(association.source_spans, offset),
                }
                for association in item.associations
            ],
            "warning_ids": list(item.warning_ids),
            "rendered_members": member_paths[item.candidate_id],
        }
        for item in figures.candidates
    ]
    table_records = [
        {
            "candidate_id": item.candidate_id,
            "boundary_kind": item.boundary_kind.value,
            "evidence_status": item.evidence_status.value,
            "confidence": item.confidence,
            "source_label": item.source_label,
            "source_spans": spans(item.source_spans, offset),
            "region_evidence_ids": [
                region.region_evidence_id for region in item.regions
            ],
            "associations": [
                {
                    "association_id": association.association_id,
                    "role": association.role.value,
                    "block_id": association.block_id,
                    "text": association.text,
                    "source_spans": spans(association.source_spans, offset),
                }
                for association in item.associations
            ],
            "warning_ids": list(item.warning_ids),
            "rendered_members": member_paths[item.candidate_id],
        }
        for item in tables.candidates
    ]
    assembly_records = []
    primary_members = []
    for ordinal, item in enumerate(assemblies.assemblies, 1):
        proposed_primary = (
            item.kind is EquationAssemblyKind.DISPLAY
            and not item.rejected
            and all(
                status is EquationEvidenceStatus.PROPOSED
                for status in item.detector_evidence_statuses
            )
        )
        disposition = (
            "proposed_primary_recognition"
            if proposed_primary
            else (
                "deferred_prefilter_rejected"
                if item.rejected
                else "retained_non_primary"
            )
        )
        rendered_path = None
        if proposed_primary:
            member_path = (
                Path("primary-equations") / f"assembly-{ordinal:03d}.png"
            )
            payload = item.rendered_region.content
            create_once(directory / member_path, payload)
            rendered_path = str(member_path)
            primary_members.append(
                {
                    "path": rendered_path,
                    "assembly_id": item.assembly_id,
                    "bytes": len(payload),
                    "sha256": digest(payload),
                }
            )
        assembly_records.append(
            {
                "assembly_id": item.assembly_id,
                "candidate_ids": list(item.candidate_ids),
                "kind": item.kind.value,
                "page_index": offset + item.page_index,
                "source_spans": spans(item.source_spans, offset),
                "source_block_ids": list(item.source_block_ids),
                "raw_fragments": list(item.raw_fragments),
                "sanitized_native_text": item.sanitized_native_text,
                "source_labels": list(item.source_labels),
                "prefilter_reasons": list(item.prefilter_reasons),
                "rejected": item.rejected,
                "disposition": disposition,
                "rendered_member": rendered_path,
            }
        )
    all_candidate_ids = {
        item["candidate_id"]
        for item in equation_records + figure_records + table_records
    }
    if all_candidate_ids != set(member_paths):
        raise RuntimeError(
            f"{name} chunk {number}: candidate/member coverage differs"
        )
    covered_equations = [
        candidate_id
        for item in assembly_records
        for candidate_id in item["candidate_ids"]
    ]
    if len(covered_equations) != len(equation_records) or set(
        covered_equations
    ) != {item["candidate_id"] for item in equation_records}:
        raise RuntimeError(f"{name} chunk {number}: assembly coverage differs")
    body = {
        "contract_version": "1.0",
        "book": name,
        "chunk_number": number,
        "chunk_plan_id": chunk["chunk_plan_id"],
        "evidence_inventory_id": evidence_inventory["inventory_id"],
        "equation_assembly_result_id": assemblies.artifact_id,
        "equations": equation_records,
        "figures": figure_records,
        "tables": table_records,
        "equation_assemblies": assembly_records,
        "primary_recognition_members": primary_members,
        "disposition_counts": {
            "proposed_primary_recognition": sum(
                item["disposition"] == "proposed_primary_recognition"
                for item in assembly_records
            ),
            "deferred_prefilter_rejected": sum(
                item["disposition"] == "deferred_prefilter_rejected"
                for item in assembly_records
            ),
            "retained_non_primary": sum(
                item["disposition"] == "retained_non_primary"
                for item in assembly_records
            ),
        },
    }
    value = {
        **body,
        "quality_inventory_id": identity(
            "reference-multimodal-quality-inventory", body
        ),
    }
    json_once(path, value)
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book")
    args = parser.parse_args()
    plan = json.loads(exact(PLAN_PATH))
    values = []
    for book in plan["books"]:
        if args.book and args.book != book["book"]:
            continue
        source = exact(REFERENCE_ROOT / book["source_sha256"] / "document.pdf")
        if digest(source) != book["source_sha256"]:
            raise RuntimeError(f"{book['book']}: source changed")
        for chunk in book["chunks"]:
            value = process(book, chunk, source)
            values.append(value)
            counts = value["disposition_counts"]
            print(
                f"{book['book']} {chunk['chunk_number']}/{len(book['chunks'])}: primary={counts['proposed_primary_recognition']} deferred={counts['deferred_prefilter_rejected']} retained={counts['retained_non_primary']}",
                flush=True,
            )
    summary_body = {
        "contract_version": "1.0",
        "preparation_plan_id": plan["plan_id"],
        "books": sorted({item["book"] for item in values}),
        "quality_inventory_ids": [
            item["quality_inventory_id"] for item in values
        ],
        "chunk_count": len(values),
        "equation_candidate_count": sum(
            len(item["equations"]) for item in values
        ),
        "figure_candidate_count": sum(len(item["figures"]) for item in values),
        "table_candidate_count": sum(len(item["tables"]) for item in values),
        "equation_assembly_count": sum(
            len(item["equation_assemblies"]) for item in values
        ),
        "proposed_primary_recognition_count": sum(
            item["disposition_counts"]["proposed_primary_recognition"]
            for item in values
        ),
        "deferred_prefilter_rejected_count": sum(
            item["disposition_counts"]["deferred_prefilter_rejected"]
            for item in values
        ),
        "retained_non_primary_count": sum(
            item["disposition_counts"]["retained_non_primary"]
            for item in values
        ),
        "primary_member_bytes": sum(
            member["bytes"]
            for item in values
            for member in item["primary_recognition_members"]
        ),
        "limitations": [
            "automated_unreviewed",
            "proposed_not_accepted",
            "no_model_execution",
        ],
    }
    summary = {
        **summary_body,
        "quality_summary_id": identity(
            "reference-multimodal-quality-summary", summary_body
        ),
    }
    suffix = "all" if args.book is None else args.book
    output = ROOT / f"quality-summary-{suffix}.json"
    status = json_once(output, summary)
    print(
        json.dumps(
            {"status": status, "sha256": digest(exact(output)), **summary},
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
