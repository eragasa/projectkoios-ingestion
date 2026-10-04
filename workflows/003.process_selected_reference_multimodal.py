#!/Users/eugene/repos/projectkoios-ingestion/.venv/bin/python
from __future__ import annotations

import argparse
import fcntl
import hashlib
import html
import json
import math
import os
import sys
import time
import traceback
from dataclasses import dataclass, replace
from io import BytesIO
from pathlib import Path

import pymupdf
from projectkoios.ingestion import (
    CleanTranscriptRequest,
    DeterministicArticleStructureAnalyzer,
    DeterministicCleanTranscriptProjector,
    DeterministicEquationAssembler,
    DeterministicEquationCandidateDetector,
    DeterministicFigureCandidateDetector,
    DeterministicLayoutProcessor,
    DeterministicStructuredTranscriptionComposer,
    DeterministicTableStructureReconstructor,
    EquationAssemblyArtifact,
    EquationAssemblyKind,
    EquationEvidenceStatus,
    FigureDetectionConfiguration,
    LayoutConfiguration,
    PageRegionSelection,
    PyMuPdfExtractor,
    SourceDocument,
    TableDetectionConfiguration,
    TableDetectionInput,
    TableDetectionResult,
    TablePageRuleEvidence,
    build_equation_index,
    serialize_contract,
)
from projectkoios.ingestion.equation_enrichment import (
    EQUATION_ENRICHMENT_CONTRACT_VERSION,
    EquationEnrichmentInventoryStatus,
    EquationRecognitionCheckpoint,
    EquationRecognitionError,
    EquationRecognitionRequest,
    EquationRecognitionWorkState,
    defer_equation_recognition,
    require_equation_enrichment_inventory,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.pix2tex.recognizer import (
    Pix2TexCliEquationRecognizer,
)
from projectkoios.ingestion.integrations.sqlite.processing_state.store import (
    SqliteProcessingStateStore,
)
from projectkoios.ingestion.pdf.adapters.pymupdf.rendering import (
    PyMuPdfRegionRenderer,
)
from projectkoios.ingestion.storage.processing_state.base import (
    AbstractProcessingStateStore,
)
from projectkoios.ingestion.storage.processing_state.contracts import (
    ProcessingBookRegistration,
    ProcessingBookState,
    ProcessingCandidateState,
    ProcessingChunkState,
    ProcessingEventDraft,
    ProcessingStateInitializationRequest,
    ProcessingStateLoadRequest,
    ProcessingStateSaveRequest,
    ProcessingStateSnapshot,
)
from projectkoios.ingestion.transcription import StructuredTranscriptionRequest

ARTIFACT_ROOT = Path(
    "/Users/eugene/projects/projectkoios/artifacts/reference-multimodal-v1"
)
REFERENCE_ROOT = Path("/Users/eugene/projects/projectkoios/references")
TEXT_ROOT = Path(
    "/Users/eugene/projects/projectkoios/artifacts/reference-page-resolution-v1/objects"
)
DATABASE = ARTIFACT_ROOT / "status.sqlite3"
PROGRESS = ARTIFACT_ROOT / "progress.json"
STATUS_HTML = ARTIFACT_ROOT / "status.html"
LOCK = ARTIFACT_ROOT / "selected-books.lock"
CHUNK_PAGES = 10
PIX2TEX_ROOT = Path(
    "/Users/eugene/.local/share/uv/tools/pix2tex/lib/python3.12/site-packages/pix2tex/model"
)
PIX2TEX_EXE = Path("/Users/eugene/.local/bin/pix2tex_cli")
PIX2TEX_RESOURCES = (
    ("configuration", PIX2TEX_ROOT / "settings/config.yaml"),
    ("tokenizer", PIX2TEX_ROOT / "dataset/tokenizer.json"),
    ("model", PIX2TEX_ROOT / "checkpoints/weights.pth"),
    ("image-resizer", PIX2TEX_ROOT / "checkpoints/image_resizer.pth"),
)


@dataclass(frozen=True)
class Book:
    order: int
    name: str
    digest: str
    pages: int
    chunk_pages: int = CHUNK_PAGES

    @property
    def root(self) -> Path:
        return ARTIFACT_ROOT / self.name

    @property
    def source(self) -> Path:
        return REFERENCE_ROOT / self.digest / "document.pdf"

    @property
    def baseline(self) -> Path:
        return (
            TEXT_ROOT
            / self.digest[:2]
            / self.digest
            / "composed-transcript.json"
        )

    @property
    def chunks(self) -> int:
        return math.ceil(self.pages / self.chunk_pages)


BOOKS = (
    Book(
        1,
        "SimonSS1Ed",
        "46807198536b8672000463b8d9c8ae555f4955ba0ad0e80cec19b01671030be2",
        305,
    ),
    Book(
        2,
        "AshcroftMermin_SolidStatePhysics",
        "6299153bde8e4ee49583ca8abfcc9afd687a34c25a0d06252681200fbda781ad",
        848,
    ),
    Book(
        3,
        "Marder2Ed",
        "bc1ce37437da489aa1b35b5fe86750cf3bd35a9c0c9df7597b1e55871a243d93",
        985,
    ),
    Book(
        4,
        "SzeNg3Ed",
        "7909c81fe5c12006dbaf4f664b029b67319bd7c45fe86d97ccedaf229067a221",
        763,
    ),
    Book(
        5,
        "Neaman3Ed",
        "31dce1ae5f09199951a496da12d00f7873f0ccbce00f3cd67449438b187d3761",
        566,
        chunk_pages=5,
    ),
    Book(
        6,
        "SzeLee3Ed",
        "539257eb20229bee438dbd628e017bcf8ba6bb6348198ce1e9000cd685d7263e",
        590,
    ),
    Book(
        7,
        "YuCardona4Ed",
        "acfc317504ba1e20a14686c9cbf66b542fb844b4d29b9cc66307598961963f30",
        793,
    ),
    Book(
        8,
        "RudanPhysicsSemiconductors",
        "53960e40556225a3b56cbd601409d737eb0f8384026550dce0bc16ef7aca7014",
        648,
    ),
)


def now() -> float:
    return time.time()


def atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
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


def atomic_json(path: Path, value: object) -> None:
    atomic_bytes(
        path,
        (
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n"
        ).encode(),
    )


def owner_json(path: Path, value: object) -> None:
    atomic_bytes(path, (serialize_contract(value) + "\n").encode())


def connect() -> AbstractProcessingStateStore:
    store = SqliteProcessingStateStore(database=DATABASE)
    store.initialize(
        request=ProcessingStateInitializationRequest.create(
            registrations=tuple(
                ProcessingBookRegistration(
                    name=book.name,
                    queue_order=book.order,
                    pages=book.pages,
                    chunk_pages=book.chunk_pages,
                )
                for book in BOOKS
            ),
            created=now(),
        )
    )
    return store


def load_state(store: AbstractProcessingStateStore) -> ProcessingStateSnapshot:
    return store.load(
        request=ProcessingStateLoadRequest.create(
            book_names=tuple(book.name for book in BOOKS)
        )
    )


def save_state(
    store: AbstractProcessingStateStore,
    previous: ProcessingStateSnapshot,
    *,
    books: tuple[ProcessingBookState, ...] | None = None,
    chunks: tuple[ProcessingChunkState, ...] | None = None,
    candidates: tuple[ProcessingCandidateState, ...] | None = None,
    events: tuple[ProcessingEventDraft, ...] = (),
) -> ProcessingStateSnapshot:
    intended = ProcessingStateSnapshot.create(
        books=previous.books if books is None else books,
        chunks=previous.chunks if chunks is None else chunks,
        candidates=previous.candidates if candidates is None else candidates,
    )
    return store.save(
        request=ProcessingStateSaveRequest.create(
            expected_snapshot_id=previous.snapshot_id,
            snapshot=intended,
            events=events,
        )
    ).snapshot


def replace_book_state(
    snapshot: ProcessingStateSnapshot,
    value: ProcessingBookState,
) -> tuple[ProcessingBookState, ...]:
    return tuple(
        value if item.name == value.name else item for item in snapshot.books
    )


def replace_chunk_state(
    snapshot: ProcessingStateSnapshot,
    value: ProcessingChunkState,
) -> tuple[ProcessingChunkState, ...]:
    return tuple(
        value
        if (item.book, item.chunk_number) == (value.book, value.chunk_number)
        else item
        for item in snapshot.chunks
    )


def book_state(
    snapshot: ProcessingStateSnapshot, name: str
) -> ProcessingBookState:
    return next(item for item in snapshot.books if item.name == name)


def chunk_state(
    snapshot: ProcessingStateSnapshot,
    book: str,
    chunk_number: int,
) -> ProcessingChunkState:
    return next(
        item
        for item in snapshot.chunks
        if (item.book, item.chunk_number) == (book, chunk_number)
    )


def check_book(book: Book) -> tuple[bytes, dict[str, object]]:
    if book.source.is_symlink() or not book.source.is_file():
        raise RuntimeError(f"{book.name}: source PDF missing or unsafe")
    content = book.source.read_bytes()
    if hashlib.sha256(content).hexdigest() != book.digest:
        raise RuntimeError(f"{book.name}: source PDF identity changed")
    baseline = json.loads(book.baseline.read_text(encoding="utf-8"))
    if (
        baseline.get("complete") is not True
        or baseline.get("page_count") != book.pages
    ):
        raise RuntimeError(f"{book.name}: composed baseline incomplete")
    if len(baseline.get("pages", ())) != book.pages:
        raise RuntimeError(f"{book.name}: composed page coverage incomplete")
    return content, baseline


def chunk_dir(book: Book, chunk: int) -> Path:
    return book.root / "chunks" / f"chunk-{chunk:03d}"


def make_chunk(book: Book, original: bytes, chunk: int) -> bytes:
    path = chunk_dir(book, chunk) / "source.pdf"
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise RuntimeError("unsafe derived chunk PDF")
        return path.read_bytes()
    first = (chunk - 1) * book.chunk_pages
    last = min(book.pages, first + book.chunk_pages) - 1
    source_pdf = pymupdf.open(stream=original, filetype="pdf")
    derived = pymupdf.open()
    try:
        if source_pdf.page_count != book.pages:
            raise RuntimeError(
                f"{book.name}: PDF page count differs from baseline"
            )
        derived.insert_pdf(source_pdf, from_page=first, to_page=last)
        content = derived.tobytes(garbage=4, deflate=True)
    finally:
        derived.close()
        source_pdf.close()
    atomic_bytes(path, content)
    return content


class EmptyTableRuleInspector:
    name = "private-empty-table-rule-inspector"
    version = "1"

    def inspect(self, document, content, configuration):
        del content, configuration
        return tuple(
            TablePageRuleEvidence.create(
                source=document.source,
                page_index=page.page_index,
                page_width=page.width,
                page_height=page.height,
                rotation_degrees=page.rotation_degrees,
                segments=(),
                ignored_drawing_item_count=0,
                processor_name=self.name,
                processor_version=self.version,
                backend_name="application-policy",
                backend_version="1",
            )
            for page in document.pages
        )


def load_chunk(book: Book, original: bytes, chunk: int):
    content = make_chunk(book, original, chunk)
    first = (chunk - 1) * book.chunk_pages + 1
    last = min(book.pages, first + book.chunk_pages - 1)
    source = SourceDocument.from_bytes(
        content,
        source_id=f"private:{book.name}:pages:{first:04d}-{last:04d}",
        media_type="application/pdf",
        locator=f"private://{book.name}/pages-{first:04d}-{last:04d}.pdf",
    )
    extraction = PyMuPdfExtractor(maximum_pages=book.chunk_pages).extract(
        source, BytesIO(content)
    )
    document = extraction.document
    filtered_pages = []
    omitted_geometry = 0
    for page in document.pages:
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
    document = replace(document, pages=tuple(filtered_pages))
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
    table_configuration = TableDetectionConfiguration()
    table_input = TableDetectionInput.create(
        document=document,
        layouts=layouts,
        page_rule_evidence=EmptyTableRuleInspector().inspect(
            document, BytesIO(content), table_configuration
        ),
        configuration=table_configuration,
    )
    table_detection = TableDetectionResult.create(
        detection_input=table_input,
        candidates=(),
        warnings=(),
        processor_name="private-no-table-candidates",
        processor_version="1",
    )
    tables = DeterministicTableStructureReconstructor().reconstruct(
        table_detection
    )
    structure = DeterministicArticleStructureAnalyzer().analyze_with_layout(
        document, layouts
    )
    transcription = DeterministicStructuredTranscriptionComposer().action(
        request=StructuredTranscriptionRequest.create(
            document=document,
            structure_analysis=structure,
            equation_detection_result=equations,
            table_structure_result=tables,
            figure_detection_result=figures,
        )
    )
    projector = DeterministicCleanTranscriptProjector()
    clean = projector.action(
        request=CleanTranscriptRequest.create(
            transcription_result=transcription,
            layouts=layouts,
            configuration=projector.configuration,
        )
    )
    return (
        content,
        extraction,
        equations,
        figures,
        transcription,
        clean,
        omitted_geometry,
    )


def figure_region(source, content: bytes, candidate):
    boxes = [
        component.source_bounding_box for component in candidate.components
    ]
    box = (
        min(value[0] for value in boxes),
        min(value[1] for value in boxes),
        max(value[2] for value in boxes),
        max(value[3] for value in boxes),
    )
    renderer = PyMuPdfRegionRenderer(
        max_total_pixels=25_000_000, max_total_raster_bytes=100_000_000
    )
    return renderer.render(
        source,
        BytesIO(content),
        (
            PageRegionSelection.for_bounding_box(
                source, candidate.source_spans[0].page_index, box
            ),
        ),
    )[0], box


def compact_span(span) -> dict[str, object]:
    return {
        "page_index": span.page_index,
        "bounding_box": list(span.bounding_box)
        if span.bounding_box is not None
        else None,
    }


def persist_detection(
    book: Book,
    chunk: int,
    data,
    store: AbstractProcessingStateStore,
    elapsed: float,
) -> None:
    (
        content,
        extraction,
        equations,
        figures,
        transcription,
        clean,
        omitted_geometry,
    ) = data
    directory = chunk_dir(book, chunk)
    projection = {
        "items": [
            {
                "item_kind": item.item_kind.value,
                "source_object_id": item.source_object_id,
                "page_index": item.page_index,
                "order_index": item.order_index,
                "normalized_text": item.normalized_text,
                "source_block_ids": list(item.source_block_ids),
                "source_spans": [
                    compact_span(span) for span in item.source_spans
                ],
            }
            for item in transcription.items
        ],
        "clean_exclusions": [
            {
                "page_index": item.page_index,
                "block_id": item.block_id,
                "reason": item.reason.value,
            }
            for item in clean.exclusions
        ],
        "omitted_invalid_geometry_text_blocks": omitted_geometry,
    }
    atomic_json(directory / "projection.json", projection)
    start_page = (chunk - 1) * book.chunk_pages
    snapshot = load_state(store)
    retained_candidates = tuple(
        item
        for item in snapshot.candidates
        if (item.book, item.chunk_number) != (book.name, chunk)
    )
    detected_candidates = []
    for ordinal, candidate in enumerate(equations.candidates, 1):
        source_page = start_page + candidate.source_spans[0].page_index + 1
        label = f"Equation p{source_page}-{ordinal}"
        target = directory / "equations" / f"equation-{ordinal:03d}"
        atomic_bytes(
            target / "candidate.png", candidate.rendered_region.content
        )
        atomic_json(
            target / "metadata.json",
            {
                "candidate_id": candidate.candidate_id,
                "human_label": label,
                "source_page": source_page,
                "source_block_id": candidate.source_block_id,
                "source_spans": [
                    compact_span(span) for span in candidate.source_spans
                ],
                "raw_text": candidate.raw_text,
                "source_label": candidate.source_label,
                "kind": candidate.kind.value,
                "evidence_status": candidate.evidence_status.value,
                "confidence": candidate.confidence,
                "limitations": [
                    "automated_unreviewed",
                    "candidate_not_validated",
                ],
            },
        )
        detected_candidates.append(
            ProcessingCandidateState(
                book=book.name,
                kind="equation",
                chunk_number=chunk,
                ordinal=ordinal,
                label=label,
                source_page=source_page,
                owner_id=candidate.candidate_id,
                state="detected",
                runtime_seconds=None,
                error=None,
                artifact_path=str(target.relative_to(book.root)),
                updated=now(),
            )
        )
    for ordinal, candidate in enumerate(figures.candidates, 1):
        source_page = start_page + candidate.source_spans[0].page_index + 1
        label = f"Figure p{source_page}-{ordinal}"
        target = directory / "figures" / f"figure-{ordinal:03d}"
        region, box = figure_region(
            extraction.document.source, content, candidate
        )
        atomic_bytes(target / "candidate.png", region.content)
        atomic_json(
            target / "metadata.json",
            {
                "candidate_id": candidate.candidate_id,
                "human_label": label,
                "source_page": source_page,
                "visual_box": list(box),
                "components": [
                    {
                        "component_index": component.component_index,
                        "source_bounding_box": list(
                            component.source_bounding_box
                        ),
                    }
                    for component in candidate.components
                ],
                "associations": [
                    {
                        "role": item.role.value,
                        "text": item.text,
                        "block_id": item.block_id,
                        "source_spans": [
                            compact_span(span) for span in item.source_spans
                        ],
                    }
                    for item in candidate.associations
                ],
                "evidence_status": candidate.evidence_status.value,
                "confidence": candidate.confidence,
                "limitations": [
                    "automated_unreviewed",
                    "candidate_not_validated",
                ],
            },
        )
        detected_candidates.append(
            ProcessingCandidateState(
                book=book.name,
                kind="figure",
                chunk_number=chunk,
                ordinal=ordinal,
                label=label,
                source_page=source_page,
                owner_id=candidate.candidate_id,
                state="detected",
                runtime_seconds=None,
                error=None,
                artifact_path=str(target.relative_to(book.root)),
                updated=now(),
            )
        )
    updated_chunk = replace(
        chunk_state(snapshot, book.name, chunk),
        detection_state="complete",
        equation_state="pending" if equations.candidates else "complete",
        equation_count=len(equations.candidates),
        figure_count=len(figures.candidates),
        detection_seconds=elapsed,
        error=None,
        updated=now(),
    )
    updated_chunks = replace_chunk_state(snapshot, updated_chunk)
    owned_chunks = tuple(
        item for item in updated_chunks if item.book == book.name
    )
    updated_book = replace(
        book_state(snapshot, book.name),
        stage="detection",
        state="running",
        equation_candidates=sum(item.equation_count for item in owned_chunks),
        figure_candidates=sum(item.figure_count for item in owned_chunks),
        updated=now(),
    )
    save_state(
        store,
        snapshot,
        books=replace_book_state(snapshot, updated_book),
        chunks=updated_chunks,
        candidates=retained_candidates + tuple(detected_candidates),
    )


def status(store: AbstractProcessingStateStore) -> None:
    snapshot = load_state(store)
    books: list[dict[str, object]] = []
    for book in snapshot.books:
        chunks = tuple(
            item for item in snapshot.chunks if item.book == book.name
        )
        detected = sum(item.detection_state == "complete" for item in chunks)
        equations = sum(
            item.equation_state in ("complete", "not_requested")
            for item in chunks
        )
        books.append(
            {
                "book": book.name,
                "stage": book.stage,
                "state": book.state,
                "pages": book.pages,
                "chunks_detected": detected,
                "chunks_total": book.chunks,
                "equation_chunks_complete": equations,
                "equation_candidates": book.equation_candidates,
                "figure_candidates": book.figure_candidates,
                "primary_equations": book.primary_equations,
                "paragraphs": book.paragraphs,
                "error": book.error,
            }
        )
    updated_at = time.strftime("%Y-%m-%d %H:%M:%S %Z")
    value = {
        "status": "failed"
        if any(item["state"] == "failed" for item in books)
        else (
            "complete"
            if all(item["state"] == "complete" for item in books)
            else "running"
        ),
        "updated": updated_at,
        "books": books,
    }
    atomic_json(PROGRESS, value)
    html_rows = "".join(
        "<tr>"
        + "".join(
            f"<td>{html.escape(str(item[key]))}</td>"
            for key in (
                "book",
                "stage",
                "state",
                "pages",
                "chunks_detected",
                "chunks_total",
                "equation_candidates",
                "figure_candidates",
                "primary_equations",
            )
        )
        + "</tr>"
        for item in books
    )
    document = (
        "<!doctype html><meta charset='utf-8'><title>Selected book multimodal progress</title><style>body{font:15px system-ui;margin:2rem}table{border-collapse:collapse}th,td{border:1px solid #bbb;padding:.4rem .7rem}</style><h1>Selected book multimodal progress</h1><table><thead><tr><th>Book</th><th>Stage</th><th>State</th><th>Pages</th><th>Detected</th><th>Chunks</th><th>Equations</th><th>Figures</th><th>Primary</th></tr></thead><tbody>"
        + html_rows
        + f"</tbody></table><p>Updated {html.escape(updated_at)}</p>"
    )
    atomic_bytes(STATUS_HTML, document.encode())


def detect_book(
    book: Book,
    original: bytes,
    store: AbstractProcessingStateStore,
) -> None:
    snapshot = load_state(store)
    pending = tuple(
        item.chunk_number
        for item in snapshot.chunks
        if item.book == book.name and item.detection_state != "complete"
    )
    for chunk in pending:
        started = time.monotonic()
        try:
            data = load_chunk(book, original, chunk)
            persist_detection(
                book, chunk, data, store, time.monotonic() - started
            )
        except Exception as error:
            message = f"{type(error).__name__}: {error}"
            snapshot = load_state(store)
            failed_chunk = replace(
                chunk_state(snapshot, book.name, chunk),
                detection_state="failed",
                error=message,
                updated=now(),
            )
            failed_book = replace(
                book_state(snapshot, book.name),
                stage="detection",
                state="failed",
                error=message,
                updated=now(),
            )
            save_state(
                store,
                snapshot,
                books=replace_book_state(snapshot, failed_book),
                chunks=replace_chunk_state(snapshot, failed_chunk),
            )
            status(store)
            raise
        status(store)
    snapshot = load_state(store)
    ready_book = replace(
        book_state(snapshot, book.name),
        stage="detected",
        state="ready",
        updated=now(),
    )
    save_state(
        store,
        snapshot,
        books=replace_book_state(snapshot, ready_book),
    )
    status(store)


def pix2tex() -> Pix2TexCliEquationRecognizer:
    return Pix2TexCliEquationRecognizer(
        PIX2TEX_EXE,
        backend_version="0.1.4",
        resources=PIX2TEX_RESOURCES,
        timeout_seconds=3600,
    )


def one_assembly(
    artifact: EquationAssemblyArtifact, assembly
) -> EquationAssemblyArtifact:
    identity = stable_id(
        "equation-assembly-artifact",
        EQUATION_ENRICHMENT_CONTRACT_VERSION,
        artifact.source_id,
        artifact.source_content_hash,
        artifact.document_id,
        artifact.detection_result_id,
        (assembly.assembly_id,),
    )
    return EquationAssemblyArtifact(
        artifact_id=identity,
        source_id=artifact.source_id,
        source_content_hash=artifact.source_content_hash,
        document_id=artifact.document_id,
        detection_result_id=artifact.detection_result_id,
        assemblies=(assembly,),
    )


def smoke_simon(store: AbstractProcessingStateStore) -> dict[str, object]:
    book = BOOKS[0]
    original, _baseline = check_book(book)
    detect_book(book, original, store)
    snapshot = load_state(store)
    figure_row = next(
        iter(
            sorted(
                (
                    item
                    for item in snapshot.candidates
                    if item.book == book.name and item.kind == "figure"
                ),
                key=lambda item: (item.source_page, item.ordinal),
            )
        ),
        None,
    )
    if figure_row is None:
        raise RuntimeError("Simon smoke requires one figure candidate")
    selected = None
    selected_assembly = None
    equation_label = None
    equation_chunks = tuple(
        item.chunk_number
        for item in snapshot.chunks
        if item.book == book.name and item.equation_count > 0
    )
    for chunk_number in equation_chunks:
        data = load_chunk(book, original, chunk_number)
        content, _extraction, equations = data[:3]
        assembly = DeterministicEquationAssembler(
            renderer=PyMuPdfRegionRenderer()
        ).assemble(equations, content)
        selected_assembly = next(
            (
                item
                for item in assembly.assemblies
                if item.kind is EquationAssemblyKind.DISPLAY
                and not item.rejected
                and all(
                    status is EquationEvidenceStatus.PROPOSED
                    for status in item.detector_evidence_statuses
                )
            ),
            None,
        )
        if selected_assembly is not None:
            selected = one_assembly(assembly, selected_assembly)
            candidate_id = selected_assembly.candidate_ids[0]
            label_row = next(
                (
                    item
                    for item in snapshot.candidates
                    if item.book == book.name
                    and item.kind == "equation"
                    and item.owner_id == candidate_id
                ),
                None,
            )
            equation_label = (
                label_row.label if label_row is not None else candidate_id
            )
            break
    if selected is None or selected_assembly is None or equation_label is None:
        raise RuntimeError("Simon smoke requires one primary-eligible equation")
    recognizer = pix2tex()
    recognition_request = EquationRecognitionRequest.create(
        assembly_artifact=selected,
        processor_identity=recognizer.identity,
    )
    started = time.monotonic()
    recognition = recognizer.action(request=recognition_request)
    equation_seconds = time.monotonic() - started
    smoke_root = book.root / "smoke"
    atomic_bytes(
        smoke_root / "equation.png",
        selected_assembly.rendered_region.content,
    )
    owner_json(smoke_root / "equation-recognition.json", recognition)
    figure_png = book.root / figure_row.artifact_path / "candidate.png"
    if not figure_png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("Simon figure smoke PNG is invalid")
    book_chunks = tuple(
        item for item in snapshot.chunks if item.book == book.name
    )
    summary = {
        "status": "succeeded",
        "book": book.name,
        "equation_label": equation_label,
        "figure_label": figure_row.label,
        "pix2tex_seconds": equation_seconds,
        "equation_candidates": sum(item.equation_count for item in book_chunks),
        "figure_candidates": sum(item.figure_count for item in book_chunks),
        "pages": book.pages,
        "limitations": [
            "automated_unreviewed",
            "smoke_only",
            "no_figure_model_call",
        ],
    }
    atomic_json(smoke_root / "summary.json", summary)
    event_created = now()
    completed_book = replace(
        book_state(snapshot, book.name),
        stage="smoke_complete",
        state="ready",
        updated=event_created,
    )
    save_state(
        store,
        snapshot,
        books=replace_book_state(snapshot, completed_book),
        events=(
            ProcessingEventDraft.create(
                created=event_created,
                book=book.name,
                label="Smoke complete",
                detail=(
                    f"Pix2Tex {equation_seconds:.1f}s; deterministic figure "
                    "PNG validated"
                ),
            ),
        ),
    )
    status(store)
    return summary


def enrich_equations(
    book: Book,
    original: bytes,
    store: AbstractProcessingStateStore,
) -> None:
    recognizer = pix2tex()
    snapshot = load_state(store)
    chunks = tuple(
        item.chunk_number
        for item in snapshot.chunks
        if item.book == book.name
        and item.equation_count > 0
        and item.equation_state != "complete"
    )
    running_book = replace(
        book_state(snapshot, book.name),
        stage="equations",
        state="running",
        updated=now(),
    )
    save_state(
        store,
        snapshot,
        books=replace_book_state(snapshot, running_book),
    )
    status(store)
    for chunk in chunks:
        started = time.monotonic()
        try:
            data = load_chunk(book, original, chunk)
            content, _extraction, equations = data[:3]
            assembly = DeterministicEquationAssembler(
                renderer=PyMuPdfRegionRenderer()
            ).assemble(equations, content)
            recognition_request = EquationRecognitionRequest.create(
                assembly_artifact=assembly,
                processor_identity=recognizer.identity,
            )
            recognition = recognizer.action(request=recognition_request)
            index = build_equation_index(assembly, recognition)
            target = chunk_dir(book, chunk) / "equation-enrichment"
            owner_json(target / "recognition.json", recognition)
            owner_json(target / "index.json", index)
            atomic_json(
                target / "assemblies.json",
                {
                    "assemblies": [
                        {
                            "ordinal": ordinal,
                            "assembly_id": item.assembly_id,
                            "candidate_ids": list(item.candidate_ids),
                            "page_index": item.page_index,
                            "source_block_ids": list(item.source_block_ids),
                            "source_bounding_box": list(
                                item.rendered_region.source_bounding_box
                            ),
                            "sanitized_native_text": item.sanitized_native_text,
                        }
                        for ordinal, item in enumerate(assembly.assemblies, 1)
                    ]
                },
            )
            for ordinal, item in enumerate(assembly.assemblies, 1):
                atomic_bytes(
                    target / f"assembly-{ordinal:03d}.png",
                    item.rendered_region.content,
                )
            elapsed = time.monotonic() - started
            snapshot = load_state(store)
            completed_chunk = replace(
                chunk_state(snapshot, book.name, chunk),
                equation_state="complete",
                equation_seconds=elapsed,
                error=None,
                updated=now(),
            )
            completed_candidates = tuple(
                replace(
                    item,
                    state="complete",
                    runtime_seconds=elapsed,
                    error=None,
                    updated=now(),
                )
                if item.book == book.name
                and item.kind == "equation"
                and item.chunk_number == chunk
                else item
                for item in snapshot.candidates
            )
            save_state(
                store,
                snapshot,
                chunks=replace_chunk_state(snapshot, completed_chunk),
                candidates=completed_candidates,
            )
            status(store)
        except EquationRecognitionError as error:
            _fail_equation_chunk(store, book, chunk, error)
            raise
        except Exception as error:
            _fail_equation_chunk(store, book, chunk, error)
            raise
    snapshot = load_state(store)
    completed_figures = tuple(
        replace(
            item,
            state="detected_unreviewed",
            runtime_seconds=0.0,
            error=None,
            updated=now(),
        )
        if item.book == book.name and item.kind == "figure"
        else item
        for item in snapshot.candidates
    )
    save_state(store, snapshot, candidates=completed_figures)
    status(store)


def _fail_equation_chunk(
    store: AbstractProcessingStateStore,
    book: Book,
    chunk: int,
    error: Exception,
) -> None:
    message = f"{type(error).__name__}: {error}"
    snapshot = load_state(store)
    failed_chunk = replace(
        chunk_state(snapshot, book.name, chunk),
        equation_state="failed",
        error=message,
        updated=now(),
    )
    failed_book = replace(
        book_state(snapshot, book.name),
        stage="equations",
        state="failed",
        error=message,
        updated=now(),
    )
    save_state(
        store,
        snapshot,
        books=replace_book_state(snapshot, failed_book),
        chunks=replace_chunk_state(snapshot, failed_chunk),
    )
    status(store)


def defer_equations(
    book: Book,
    store: AbstractProcessingStateStore,
) -> None:
    snapshot = load_state(store)
    rows = tuple(
        item
        for item in snapshot.chunks
        if item.book == book.name and item.detection_state == "complete"
    )
    empty_chunks_to_complete = []
    chunks_to_defer = []
    for row in rows:
        target = chunk_dir(book, row.chunk_number) / "equation-enrichment"
        inventory = require_equation_enrichment_inventory(target)
        state = EquationRecognitionWorkState(row.equation_state)
        checkpoint = EquationRecognitionCheckpoint(state=state, error=row.error)
        if inventory.status is EquationEnrichmentInventoryStatus.COMPLETE_PAIR:
            if state is not EquationRecognitionWorkState.COMPLETE:
                raise ValueError(
                    "complete equation enrichment pair has "
                    f"{state.value} state in chunk {row.chunk_number}"
                )
            continue
        if (
            state is EquationRecognitionWorkState.COMPLETE
            and row.equation_count
        ):
            raise ValueError(
                "completed equation state lacks enrichment artifacts in "
                f"chunk {row.chunk_number}"
            )
        if not row.equation_count:
            if state is EquationRecognitionWorkState.PENDING:
                empty_chunks_to_complete.append(row.chunk_number)
            continue
        decision = defer_equation_recognition(checkpoint)
        if decision.previous_state is EquationRecognitionWorkState.FAILED:
            raise ValueError(
                "failed equation checkpoint preserved in chunk "
                f"{row.chunk_number}: {decision.preserved_error}"
            )
        if decision.changed:
            chunks_to_defer.append(row.chunk_number)
    changed_chunks = []
    for row in snapshot.chunks:
        if (
            row.book == book.name
            and row.chunk_number in empty_chunks_to_complete
        ):
            if row.equation_state != "pending" or row.error is not None:
                raise ValueError(
                    "empty equation checkpoint changed during deferral"
                )
            changed_chunks.append(
                replace(
                    row,
                    equation_state="complete",
                    equation_seconds=row.equation_seconds or 0.0,
                    updated=now(),
                )
            )
        elif row.book == book.name and row.chunk_number in chunks_to_defer:
            if row.equation_state != "pending" or row.error is not None:
                raise ValueError("equation checkpoint changed during deferral")
            changed_chunks.append(
                replace(
                    row,
                    equation_state="not_requested",
                    equation_seconds=row.equation_seconds or 0.0,
                    updated=now(),
                )
            )
        else:
            changed_chunks.append(row)
    changed_candidates = tuple(
        replace(
            item,
            state="detected_unreviewed_not_requested",
            runtime_seconds=item.runtime_seconds or 0.0,
            updated=now(),
        )
        if item.book == book.name
        and item.kind == "equation"
        and item.chunk_number in chunks_to_defer
        and item.state == "detected"
        and item.error is None
        else replace(
            item,
            state="detected_unreviewed",
            runtime_seconds=item.runtime_seconds or 0.0,
            updated=now(),
        )
        if item.book == book.name
        and item.kind == "figure"
        and item.state == "detected"
        and item.error is None
        else item
        for item in snapshot.candidates
    )
    projection_book = replace(
        book_state(snapshot, book.name),
        stage="projection",
        state="running",
        error=None,
        updated=now(),
    )
    save_state(
        store,
        snapshot,
        books=replace_book_state(snapshot, projection_book),
        chunks=tuple(changed_chunks),
        candidates=changed_candidates,
    )
    status(store)


def compact_text(value: str) -> str:
    return " ".join(value.split())


def overlaps_region(box: list[float], region_box: list[float]) -> bool:
    x0, y0, x1, y1 = box
    rx0, ry0, rx1, ry1 = region_box
    center_inside = rx0 <= (x0 + x1) / 2 <= rx1 and ry0 <= (y0 + y1) / 2 <= ry1
    intersection = max(0.0, min(x1, rx1) - max(x0, rx0)) * max(
        0.0, min(y1, ry1) - max(y0, ry0)
    )
    area = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    return center_inside or (area > 0 and intersection / area >= 0.5)


def padded_box(box: list[float]) -> list[float]:
    width = box[2] - box[0]
    height = box[3] - box[1]
    xp = min(48.0, max(6.0, width * 0.15))
    yp = min(48.0, max(6.0, height * 0.15))
    return [
        max(0.0, box[0] - xp),
        max(0.0, box[1] - yp),
        box[2] + xp,
        box[3] + yp,
    ]


def build_reading(
    book: Book,
    original: bytes,
    baseline: dict[str, object],
    store: AbstractProcessingStateStore,
) -> dict[str, object]:
    snapshot = load_state(store)
    reading_book = replace(
        book_state(snapshot, book.name),
        stage="reading_transcript",
        state="running",
        updated=now(),
    )
    snapshot = save_state(
        store,
        snapshot,
        books=replace_book_state(snapshot, reading_book),
    )
    status(store)
    source_pdf = pymupdf.open(stream=original, filetype="pdf")
    try:
        if source_pdf.page_count != book.pages:
            raise ValueError("reading source page count changed")
        page_dimensions = tuple(
            (float(page.cropbox.width), float(page.cropbox.height))
            for page in source_pdf
        )
    finally:
        source_pdf.close()
    pages = []
    counts = {
        key: 0
        for key in (
            "paragraphs",
            "headings",
            "figures",
            "primary_equations",
            "clean_exclusions",
            "figure_region_suppressed",
            "caption_padding_suppressed",
            "association_geometry_suppressed",
            "equation_geometry_suppressed",
            "page_labels_suppressed",
            "figure_evidence_total",
            "figure_evidence_omitted_unassociated",
            "figure_evidence_omitted_page_background",
            "figure_evidence_omitted_non_reading_scale",
            "figure_evidence_omitted_duplicate_caption",
        )
    }
    tier_counts = {
        "primary": 0,
        "auxiliary": 0,
        "rejected": 0,
        "failed": 0,
        "not_requested": 0,
    }
    for chunk in range(1, book.chunks + 1):
        offset = (chunk - 1) * book.chunk_pages
        projection = json.loads(
            (chunk_dir(book, chunk) / "projection.json").read_text()
        )
        items_by_page = {}
        for item in projection["items"]:
            items_by_page.setdefault(item["page_index"], []).append(item)
        exclusions = {}
        for item in projection["clean_exclusions"]:
            exclusions.setdefault(item["page_index"], set()).add(
                item["block_id"]
            )
            counts["clean_exclusions"] += 1
        eq_by_page = {}
        enrichment_root = chunk_dir(book, chunk) / "equation-enrichment"
        enrichment_inventory = require_equation_enrichment_inventory(
            enrichment_root
        )
        index_path = enrichment_root / "index.json"
        if (
            enrichment_inventory.status
            is EquationEnrichmentInventoryStatus.COMPLETE_PAIR
        ):
            index = json.loads(index_path.read_text())
            recognition = json.loads(
                (index_path.parent / "recognition.json").read_text()
            )
            proposals = {x["assembly_id"]: x for x in recognition["proposals"]}
            for proposal in recognition["proposals"]:
                if proposal["status"] in ("failed", "not_requested"):
                    tier_counts[proposal["status"]] += 1
            for ordinal, record in enumerate(index["records"], 1):
                tier_counts[record["tier"]] += 1
                proposal_status = proposals[record["assembly_id"]]["status"]
                if proposal_status == "failed" or (
                    record["tier"] == "primary"
                    and proposal_status == "proposed"
                ):
                    eq_by_page.setdefault(record["page_index"], []).append(
                        (ordinal, record, proposal_status)
                    )
        for local in range(min(book.chunk_pages, book.pages - offset)):
            physical = offset + local + 1
            base = baseline["pages"][physical - 1]
            printed = base.get("printed_page_label")
            figure_rows = tuple(
                item
                for item in snapshot.candidates
                if item.book == book.name
                and item.kind == "figure"
                and item.source_page == physical
            )
            figures = {}
            assoc_ids = set()
            assoc_boxes = []
            fig_boxes = []
            used_caption_ids = set()
            page_width, page_height = page_dimensions[physical - 1]
            page_area = page_width * page_height
            for row in figure_rows:
                counts["figure_evidence_total"] += 1
                meta = json.loads(
                    (
                        book.root / row.artifact_path / "metadata.json"
                    ).read_text()
                )
                caption_records = [
                    x for x in meta["associations"] if x["role"] == "caption"
                ]
                if not caption_records:
                    counts["figure_evidence_omitted_unassociated"] += 1
                    continue
                exact = meta["visual_box"]
                width = exact[2] - exact[0]
                height = exact[3] - exact[1]
                area_fraction = (
                    (width * height / page_area) if page_area > 0 else 1.0
                )
                if area_fraction >= 0.80:
                    counts["figure_evidence_omitted_page_background"] += 1
                    continue
                if area_fraction < 0.005 or min(width, height) < 24.0:
                    counts["figure_evidence_omitted_non_reading_scale"] += 1
                    continue
                caption_ids = tuple(x["block_id"] for x in caption_records)
                if any(value in used_caption_ids for value in caption_ids):
                    counts["figure_evidence_omitted_duplicate_caption"] += 1
                    continue
                used_caption_ids.update(caption_ids)
                associations = [
                    {"role": x["role"], "text": compact_text(x["text"])}
                    for x in meta["associations"]
                ]
                assoc_ids.update(x["block_id"] for x in meta["associations"])
                assoc_boxes.extend(
                    span["bounding_box"]
                    for x in meta["associations"]
                    for span in x["source_spans"]
                    if span["bounding_box"] is not None
                )
                captions = [
                    x["text"] for x in associations if x["role"] == "caption"
                ]
                fig_boxes.append((exact, padded_box(exact)))
                figures[meta["candidate_id"]] = {
                    "type": "figure",
                    "png_path": f"{row.artifact_path}/candidate.png",
                    "caption": " ".join(captions),
                    "associations": associations,
                    "status": "associated_unreviewed",
                }
            equations = {}
            eq_block_ids = set()
            eq_boxes = []
            for ordinal, record, proposal_status in eq_by_page.get(local, []):
                proposed = proposal_status == "proposed"
                block = {
                    "type": "equation",
                    "latex": record["latex_proposal"] if proposed else None,
                    "mathml": record["mathml_proposal"] if proposed else None,
                    "native_text": compact_text(
                        record["sanitized_native_text"]
                    ),
                    "png_path": f"chunks/chunk-{chunk:03d}/equation-enrichment/assembly-{ordinal:03d}.png",
                    "status": "automated_unreviewed_primary_tier"
                    if proposed
                    else "recognition_failed_pending_evidence",
                    "recognition_status": proposal_status,
                    "accepted": False,
                    "review_required": True,
                    "chunk_text_eligible": False,
                }
                for cid in record["candidate_ids"]:
                    equations[cid] = block
                eq_block_ids.update(record["source_block_ids"])
                eq_boxes.append(record["source_bounding_box"])
            if (
                enrichment_inventory.status
                is EquationEnrichmentInventoryStatus.NONE
            ):
                equation_rows = tuple(
                    item
                    for item in snapshot.candidates
                    if item.book == book.name
                    and item.kind == "equation"
                    and item.source_page == physical
                )
                for row in equation_rows:
                    meta = json.loads(
                        (
                            book.root / row.artifact_path / "metadata.json"
                        ).read_text()
                    )
                    if (
                        meta["kind"] != "display"
                        or meta["evidence_status"] != "proposed"
                    ):
                        continue
                    block = {
                        "type": "equation",
                        "latex": None,
                        "mathml": None,
                        "native_text": compact_text(meta["raw_text"]),
                        "png_path": f"{row.artifact_path}/candidate.png",
                        "status": "not_requested_pending_evidence",
                        "recognition_status": "not_requested",
                        "accepted": False,
                        "review_required": True,
                        "chunk_text_eligible": False,
                    }
                    equations[meta["candidate_id"]] = block
                    tier_counts["not_requested"] += 1
                    if meta["source_block_id"]:
                        eq_block_ids.add(meta["source_block_id"])
                    eq_boxes.extend(
                        span["bounding_box"]
                        for span in meta["source_spans"]
                        if span["bounding_box"] is not None
                    )
            blocks = []
            emitted_fig = set()
            emitted_eq = set()
            for item in sorted(
                items_by_page.get(local, ()), key=lambda x: x["order_index"]
            ):
                kind = item["item_kind"]
                if kind == "page_anchor":
                    continue
                if kind == "figure":
                    figure = figures.get(item["source_object_id"])
                    if (
                        figure is not None
                        and item["source_object_id"] not in emitted_fig
                    ):
                        blocks.append(figure)
                        emitted_fig.add(item["source_object_id"])
                    continue
                if kind == "equation":
                    equation = equations.get(item["source_object_id"])
                    if equation is not None and id(equation) not in emitted_eq:
                        blocks.append(equation)
                        emitted_eq.add(id(equation))
                    continue
                if (
                    kind not in ("prose", "heading")
                    or not item["normalized_text"]
                ):
                    continue
                ids = set(item["source_block_ids"])
                spans = [
                    x["bounding_box"]
                    for x in item["source_spans"]
                    if x["bounding_box"] is not None
                ]
                if ids & exclusions.get(local, set()):
                    counts["clean_exclusions"] += 0
                    continue
                if ids & assoc_ids:
                    continue
                if any(
                    overlaps_region(box, ab)
                    for box in spans
                    for ab in assoc_boxes
                ):
                    counts["association_geometry_suppressed"] += 1
                    continue
                if ids & eq_block_ids or any(
                    overlaps_region(box, eb) for box in spans for eb in eq_boxes
                ):
                    counts["equation_geometry_suppressed"] += 1
                    continue
                exact_hit = any(
                    overlaps_region(box, exact)
                    for box in spans
                    for exact, _padded in fig_boxes
                )
                padded_hit = any(
                    overlaps_region(box, pad)
                    for box in spans
                    for _exact, pad in fig_boxes
                )
                if exact_hit or padded_hit:
                    counts["figure_region_suppressed"] += 1
                    if not exact_hit:
                        counts["caption_padding_suppressed"] += 1
                    continue
                text = item["normalized_text"]
                if printed is not None and compact_text(text) == compact_text(
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
            for cid, figure in figures.items():
                if cid not in emitted_fig:
                    blocks.append(figure)
                    emitted_fig.add(cid)
            for identity, equation in {
                id(x): x for x in equations.values()
            }.items():
                if identity not in emitted_eq:
                    blocks.append(equation)
                    emitted_eq.add(identity)
            for order, block in enumerate(blocks):
                block["order"] = order
            counts["figures"] += len(emitted_fig)
            counts["primary_equations"] += len(emitted_eq)
            pages.append(
                {
                    "physical_page": physical,
                    "printed_page": printed,
                    "citation": {
                        "physical_page": physical,
                        "printed_page": printed,
                    },
                    "blocks": blocks,
                }
            )
    if len(pages) != book.pages or [x["physical_page"] for x in pages] != list(
        range(1, book.pages + 1)
    ):
        raise ValueError("reading pages incomplete or unordered")
    lines = []
    for page in pages:
        if [x["order"] for x in page["blocks"]] != list(
            range(len(page["blocks"]))
        ):
            raise ValueError("block order is not contiguous")
        paragraph_values = [
            x["text"] for x in page["blocks"] if x["type"] == "paragraph"
        ]
        normalized_paragraphs = {
            compact_text(value) for value in paragraph_values
        }
        for block in page["blocks"]:
            if block["type"] in ("figure", "equation"):
                path = book.root / block["png_path"]
                if (
                    path.is_symlink()
                    or not path.is_file()
                    or not path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
                ):
                    raise ValueError("referenced PNG invalid")
            if (
                block["type"] == "figure"
                and block["caption"]
                and compact_text(block["caption"]) in normalized_paragraphs
            ):
                raise ValueError(
                    f"figure caption source projected as paragraph on physical page {page['physical_page']}"
                )
            if block["type"] == "equation":
                if (
                    block["accepted"]
                    or block["chunk_text_eligible"]
                    or not block["review_required"]
                ):
                    raise ValueError("equation review gate invalid")
                if (
                    block["native_text"]
                    and compact_text(block["native_text"])
                    in normalized_paragraphs
                ):
                    raise ValueError(
                        f"equation source block projected as paragraph on physical page {page['physical_page']}: {block['native_text']!r}"
                    )
        lines.append(
            json.dumps(page, ensure_ascii=False, separators=(",", ":"))
        )
    content = ("\n".join(lines) + "\n").encode()
    if (
        b":sha256:" in content
        or b'"owner_' in content
        or b'"source_' in content
    ):
        raise ValueError("compact output leaked owner payload")
    atomic_bytes(book.root / "reading-transcript.jsonl", content)
    summary = {
        "status": "complete",
        "book": book.name,
        "pages": book.pages,
        **counts,
        "equation_counts": tier_counts,
        "utf8_bytes": len(content),
        "output": "reading-transcript.jsonl",
        "limitations": [
            "automated_unreviewed",
            "primary_equations_evidence_only_not_chunk_text",
            "recognition_not_required_for_projection",
            "auxiliary_rejected_omitted",
            "no_invented_figure_descriptions",
        ],
    }
    atomic_json(book.root / "reading-transcript-summary.json", summary)
    snapshot = load_state(store)
    event_created = now()
    completed_book = replace(
        book_state(snapshot, book.name),
        stage="complete",
        state="complete",
        primary_equations=counts["primary_equations"],
        paragraphs=counts["paragraphs"],
        error=None,
        updated=event_created,
    )
    save_state(
        store,
        snapshot,
        books=replace_book_state(snapshot, completed_book),
        events=(
            ProcessingEventDraft.create(
                created=event_created,
                book=book.name,
                label="Complete",
                detail=(
                    f"{book.pages} pages; {counts['primary_equations']} "
                    f"primary equations; {counts['figures']} figures"
                ),
            ),
        ),
    )
    status(store)
    return summary


def run_queue(store: AbstractProcessingStateStore) -> None:
    for book in BOOKS:
        snapshot = load_state(store)
        if book_state(snapshot, book.name).state == "complete":
            continue
        started = time.monotonic()
        try:
            original, baseline = check_book(book)
            detect_book(book, original, store)
            defer_equations(book, store)
            build_reading(book, original, baseline, store)
            snapshot = load_state(store)
            current_book = book_state(snapshot, book.name)
            timed_book = replace(
                current_book,
                runtime_seconds=(
                    current_book.runtime_seconds + time.monotonic() - started
                ),
                updated=now(),
            )
            save_state(
                store,
                snapshot,
                books=replace_book_state(snapshot, timed_book),
            )
            status(store)
        except Exception as error:
            message = f"{type(error).__name__}: {error}"
            snapshot = load_state(store)
            failed_book = replace(
                book_state(snapshot, book.name),
                state="failed",
                error=message,
                updated=now(),
            )
            save_state(
                store,
                snapshot,
                books=replace_book_state(snapshot, failed_book),
            )
            status(store)
            raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("smoke-simon", "run", "status"))
    args = parser.parse_args()
    os.umask(0o077)
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    stream = LOCK.open("a+b")
    try:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("selected-book workflow already running", file=sys.stderr)
        return 4
    store = connect()
    try:
        if args.phase == "status":
            status(store)
            return 0
        if args.phase == "smoke-simon":
            print(json.dumps(smoke_simon(store), indent=2, sort_keys=True))
            return 0
        run_queue(store)
        return 0
    except Exception:
        traceback.print_exc()
        return 1
    finally:
        stream.close()


if __name__ == "__main__":
    raise SystemExit(main())
