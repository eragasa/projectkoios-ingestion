#!/Users/eugene/repos/projectkoios-ingestion/.venv/bin/python
from __future__ import annotations

import argparse
import json
import os
from dataclasses import replace
from io import BytesIO
from pathlib import Path

import pymupdf
from projectkoios.ingestion import (
    DeterministicEquationCandidateDetector,
    DeterministicFigureCandidateDetector,
    DeterministicLayoutProcessor,
    DeterministicTableCandidateDetector,
    FigureDetectionConfiguration,
    LayoutConfiguration,
    PageRegionSelection,
    PyMuPdfExtractor,
    SourceDocument,
    TableDetectionConfiguration,
)
from projectkoios.ingestion.pdf.adapters.pymupdf.rendering import (
    PyMuPdfRegionRenderer,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter

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
    return SHA256Fingerprinter.fingerprint(content=content)


def identity(namespace: str, value: object) -> str:
    return f"{namespace}:sha256:{digest(canonical(value))}"


def exact_file(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"missing or unsafe file: {path}")
    return path.read_bytes()


def create_once(path: Path, content: bytes) -> str:
    if path.exists():
        if (
            path.is_symlink()
            or not path.is_file()
            or path.read_bytes() != content
        ):
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


def chunk_pdf(source: bytes, first: int, last_exclusive: int) -> bytes:
    original = pymupdf.open(stream=source, filetype="pdf")
    derived = pymupdf.open()
    try:
        derived.insert_pdf(
            original, from_page=first, to_page=last_exclusive - 1
        )
        return derived.tobytes(garbage=4, deflate=True, no_new_id=True)
    finally:
        derived.close()
        original.close()


def visual_box(candidate: object) -> tuple[float, float, float, float]:
    boxes = [
        component.source_bounding_box for component in candidate.components
    ]
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def process_chunk(
    book: dict[str, object], chunk: dict[str, object], source_bytes: bytes
) -> dict[str, object]:
    name = str(book["book"])
    number = int(chunk["chunk_number"])
    first = int(chunk["first_page_index"])
    last = int(chunk["last_page_index_exclusive"])
    directory = ROOT / "books" / name / "chunks" / f"chunk-{number:03d}"
    inventory_path = directory / "inventory.json"
    if inventory_path.exists():
        inventory_bytes = exact_file(inventory_path)
        inventory = json.loads(inventory_bytes)
        source_content = exact_file(
            directory / inventory["derived_source_path"]
        )
        if (
            len(source_content) != inventory["chunk_pdf_bytes"]
            or digest(source_content) != inventory["chunk_pdf_sha256"]
        ):
            raise RuntimeError(
                f"{name} chunk {number}: retained derived source differs"
            )
        for member in inventory["members"]:
            content = exact_file(directory / member["path"])
            if (
                len(content) != member["bytes"]
                or digest(content) != member["sha256"]
            ):
                raise RuntimeError(
                    f"{name} chunk {number}: retained member differs"
                )
        return inventory

    content = chunk_pdf(source_bytes, first, last)
    create_once(directory / "source.pdf", content)
    source = SourceDocument.from_bytes(
        content,
        source_id=f"private:{name}:pages:{first + 1:04d}-{last:04d}",
        media_type="application/pdf",
        locator=f"private://{name}/pages-{first + 1:04d}-{last:04d}.pdf",
    )
    extraction = PyMuPdfExtractor(maximum_pages=last - first).extract(
        source, BytesIO(content)
    )
    filtered_pages = []
    omitted_geometry = 0
    for page in extraction.document.pages:
        blocks = []
        for block in page.blocks:
            valid = all(
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
            if valid or block.kind != "text":
                blocks.append(block)
            else:
                omitted_geometry += 1
        filtered_pages.append(replace(page, blocks=tuple(blocks)))
    document = replace(extraction.document, pages=tuple(filtered_pages))
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
        TableDetectionConfiguration(),
        region_renderer=broad_renderer,
    ).detect_with_layout(document, BytesIO(content), layouts)

    members: list[dict[str, object]] = []
    for ordinal, candidate in enumerate(equations.candidates, 1):
        path = Path("equations") / f"equation-{ordinal:03d}.png"
        payload = candidate.rendered_region.content
        create_once(directory / path, payload)
        members.append(
            {
                "path": str(path),
                "kind": "equation",
                "candidate_id": candidate.candidate_id,
                "page_index": first + candidate.source_spans[0].page_index,
                "bytes": len(payload),
                "sha256": digest(payload),
            }
        )
    figure_renderer = PyMuPdfRegionRenderer(
        max_total_pixels=25_000_000, max_total_raster_bytes=100_000_000
    )
    for ordinal, candidate in enumerate(figures.candidates, 1):
        box = visual_box(candidate)
        rendered = figure_renderer.render(
            source,
            BytesIO(content),
            (
                PageRegionSelection.for_bounding_box(
                    source, candidate.source_spans[0].page_index, box
                ),
            ),
        )[0]
        path = Path("figures") / f"figure-{ordinal:03d}.png"
        create_once(directory / path, rendered.content)
        members.append(
            {
                "path": str(path),
                "kind": "figure",
                "candidate_id": candidate.candidate_id,
                "page_index": first + candidate.source_spans[0].page_index,
                "bytes": len(rendered.content),
                "sha256": digest(rendered.content),
            }
        )
    for ordinal, candidate in enumerate(tables.candidates, 1):
        for region_number, region in enumerate(candidate.regions, 1):
            path = (
                Path("tables")
                / f"table-{ordinal:03d}-region-{region_number:02d}.png"
            )
            payload = region.rendered_region.content
            create_once(directory / path, payload)
            members.append(
                {
                    "path": str(path),
                    "kind": "table",
                    "candidate_id": candidate.candidate_id,
                    "region_evidence_id": region.region_evidence_id,
                    "page_index": first + region.page_index,
                    "bytes": len(payload),
                    "sha256": digest(payload),
                }
            )
    members.sort(
        key=lambda item: (
            int(item["page_index"]),
            str(item["kind"]),
            str(item["candidate_id"]),
            str(item["path"]),
        )
    )
    body = {
        "contract_version": "1.0",
        "book": name,
        "source_sha256": book["source_sha256"],
        "chunk_plan_id": chunk["chunk_plan_id"],
        "chunk_number": number,
        "first_page_index": first,
        "last_page_index_exclusive": last,
        "derived_source_path": "source.pdf",
        "chunk_pdf_sha256": digest(content),
        "chunk_pdf_bytes": len(content),
        "document_id": document.document_id,
        "layout_result_ids": [layout.result_id for layout in layouts],
        "equation_detection_result_id": equations.result_id,
        "figure_detection_result_id": figures.result_id,
        "table_detection_result_id": tables.result_id,
        "equation_candidate_count": len(equations.candidates),
        "figure_candidate_count": len(figures.candidates),
        "table_candidate_count": len(tables.candidates),
        "omitted_invalid_geometry_text_blocks": omitted_geometry,
        "members": members,
        "member_bytes": sum(int(member["bytes"]) for member in members),
    }
    inventory = {
        **body,
        "inventory_id": identity("reference-multimodal-chunk-inventory", body),
    }
    json_once(inventory_path, inventory)
    return inventory


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book")
    args = parser.parse_args()
    plan_bytes = exact_file(PLAN_PATH)
    plan = json.loads(plan_bytes)
    inventories = []
    for book in plan["books"]:
        if args.book and book["book"] != args.book:
            continue
        source_path = REFERENCE_ROOT / book["source_sha256"] / "document.pdf"
        source = exact_file(source_path)
        if digest(source) != book["source_sha256"]:
            raise RuntimeError(f"{book['book']}: source changed")
        for chunk in book["chunks"]:
            inventory = process_chunk(book, chunk, source)
            inventories.append(inventory)
            print(
                f"{book['book']} {chunk['chunk_number']}/{len(book['chunks'])}: equations={inventory['equation_candidate_count']} figures={inventory['figure_candidate_count']} tables={inventory['table_candidate_count']}",
                flush=True,
            )
    summary_body = {
        "contract_version": "1.0",
        "preparation_plan_id": plan["plan_id"],
        "books": sorted({str(item["book"]) for item in inventories}),
        "chunk_inventory_ids": [item["inventory_id"] for item in inventories],
        "chunk_count": len(inventories),
        "equation_candidate_count": sum(
            int(item["equation_candidate_count"]) for item in inventories
        ),
        "figure_candidate_count": sum(
            int(item["figure_candidate_count"]) for item in inventories
        ),
        "table_candidate_count": sum(
            int(item["table_candidate_count"]) for item in inventories
        ),
        "member_count": sum(len(item["members"]) for item in inventories),
        "member_bytes": sum(int(item["member_bytes"]) for item in inventories),
    }
    summary = {
        **summary_body,
        "summary_id": identity(
            "reference-multimodal-preparation-summary", summary_body
        ),
    }
    suffix = "all" if args.book is None else args.book
    path = ROOT / f"summary-{suffix}.json"
    status = json_once(path, summary)
    content = exact_file(path)
    print(
        json.dumps(
            {
                "status": status,
                "summary_id": summary["summary_id"],
                "sha256": digest(content),
                **{
                    key: summary[key]
                    for key in (
                        "chunk_count",
                        "equation_candidate_count",
                        "figure_candidate_count",
                        "table_candidate_count",
                        "member_count",
                        "member_bytes",
                    )
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
