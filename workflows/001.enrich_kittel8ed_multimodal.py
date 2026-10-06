#!/Users/eugene/repos/projectkoios-ingestion/.venv/bin/python
from __future__ import annotations

import argparse
import fcntl
import html
import json
import os
import sqlite3
import sys
import time
import traceback
from dataclasses import replace
from io import BytesIO
from pathlib import Path

import pymupdf
from projectkoios.ingestion import (
    DeterministicArticleStructureAnalyzer,
    DeterministicEquationAssembler,
    DeterministicEquationCandidateDetector,
    DeterministicFigureCandidateDetector,
    DeterministicStructuredTranscriptionComposer,
    DeterministicTableStructureReconstructor,
    EquationAssemblyArtifact,
    PageRegionSelection,
    PyMuPdfExtractor,
    SourceDocument,
    TableDetectionConfiguration,
    TableDetectionInput,
    TableDetectionResult,
    TablePageRuleEvidence,
    build_equation_index,
    contract_dict,
    serialize_contract,
)
from projectkoios.ingestion.equation_enrichment import (
    EQUATION_ENRICHMENT_CONTRACT_VERSION,
    EquationRecognitionRequest,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.ollama.base import OllamaRequestOptions
from projectkoios.ingestion.integrations.ollama.multimodal.base import (
    OllamaMultimodalConfiguration,
    OllamaMultimodalLimits,
    OllamaMultimodalSelection,
)
from projectkoios.ingestion.integrations.ollama.multimodal.processor.region.base import (
    OllamaMultimodalRegionProcessor,
)
from projectkoios.ingestion.integrations.ollama.multimodal.processor.region.request import (
    OllamaMultimodalRegionProcessingRequest,
)
from projectkoios.ingestion.integrations.pix2tex.recognizer import (
    Pix2TexCliEquationRecognizer,
)
from projectkoios.ingestion.pdf.adapters.pymupdf import PyMuPdfRegionRenderer
from projectkoios.ingestion.sha256.verifier import SHA256Verifier
from projectkoios.ingestion.transcription import StructuredTranscriptionRequest

ROOT = Path(
    "/Users/eugene/projects/projectkoios/artifacts/reference-multimodal-v1/Kittel8ed"
)
SOURCE = Path(
    "/Users/eugene/projects/projectkoios/references/7c177d8ce281eeb1a1e0897e8d711bd908c2657ec42abd690ff1105533b7a6ed/document.pdf"
)
BASELINE = Path(
    "/Users/eugene/projects/projectkoios/artifacts/reference-page-resolution-v1/objects/7c/7c177d8ce281eeb1a1e0897e8d711bd908c2657ec42abd690ff1105533b7a6ed/composed-transcript.json"
)
EXPECTED_SOURCE_SHA256 = (
    "7c177d8ce281eeb1a1e0897e8d711bd908c2657ec42abd690ff1105533b7a6ed"
)
EXPECTED_PAGES = 700
CHUNK_PAGES = 10
DB_PATH = ROOT / "status.sqlite3"
PROGRESS = ROOT / "progress.json"
STATUS_HTML = ROOT / "status.html"
FINAL = ROOT / "enriched-transcript.json"
LOCK = ROOT / "run.lock"
OLLAMA_VERSION = "0.34.3"
OLLAMA_MODEL = "qwen3.5:9b"
OLLAMA_DIGEST = (
    "6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7"
)
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


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=FULL")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS chunks (
          chunk_number INTEGER PRIMARY KEY,
          first_page INTEGER NOT NULL,
          last_page INTEGER NOT NULL,
          detection_state TEXT NOT NULL DEFAULT 'pending',
          equation_state TEXT NOT NULL DEFAULT 'pending',
          equation_count INTEGER NOT NULL DEFAULT 0,
          figure_count INTEGER NOT NULL DEFAULT 0,
          table_count INTEGER NOT NULL DEFAULT 0,
          detection_seconds REAL,
          equation_seconds REAL,
          error TEXT,
          updated REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS candidates (
          kind TEXT NOT NULL,
          chunk_number INTEGER NOT NULL,
          ordinal INTEGER NOT NULL,
          label TEXT NOT NULL,
          source_page INTEGER NOT NULL,
          owner_id TEXT NOT NULL,
          state TEXT NOT NULL DEFAULT 'pending',
          runtime_seconds REAL,
          error TEXT,
          artifact_path TEXT NOT NULL,
          updated REAL NOT NULL,
          PRIMARY KEY(kind, chunk_number, ordinal)
        );
        CREATE TABLE IF NOT EXISTS events (
          event_number INTEGER PRIMARY KEY AUTOINCREMENT,
          created REAL NOT NULL,
          label TEXT NOT NULL,
          detail TEXT NOT NULL
        );
        """
    )
    for chunk in range(1, EXPECTED_PAGES // CHUNK_PAGES + 1):
        first = (chunk - 1) * CHUNK_PAGES + 1
        last = min(EXPECTED_PAGES, first + CHUNK_PAGES - 1)
        connection.execute(
            "INSERT OR IGNORE INTO chunks(chunk_number,first_page,last_page,updated) VALUES(?,?,?,?)",
            (chunk, first, last, now()),
        )
    connection.commit()
    return connection


def check_inputs() -> tuple[bytes, dict[str, object]]:
    if SOURCE.is_symlink() or not SOURCE.is_file():
        raise RuntimeError("Kittel source PDF is missing or unsafe")
    payload = SOURCE.read_bytes()
    if not SHA256Verifier.verify(
        content=payload, expected=EXPECTED_SOURCE_SHA256
    ):
        raise RuntimeError("Kittel source PDF identity changed")
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    if (
        baseline.get("page_count") != EXPECTED_PAGES
        or baseline.get("complete") is not True
    ):
        raise RuntimeError("Kittel composed text baseline is incomplete")
    if len(baseline.get("pages", [])) != EXPECTED_PAGES:
        raise RuntimeError("Kittel composed text page coverage is incomplete")
    return payload, baseline


def chunk_dir(chunk: int) -> Path:
    return ROOT / "chunks" / f"chunk-{chunk:03d}"


def make_chunk(original: bytes, chunk: int) -> bytes:
    path = chunk_dir(chunk) / "source.pdf"
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise RuntimeError("unsafe derived chunk path")
        return path.read_bytes()
    first = (chunk - 1) * CHUNK_PAGES
    last = min(EXPECTED_PAGES, first + CHUNK_PAGES) - 1
    source_pdf = pymupdf.open(stream=original, filetype="pdf")
    derived = pymupdf.open()
    try:
        derived.insert_pdf(source_pdf, from_page=first, to_page=last)
        content = derived.tobytes(garbage=4, deflate=True)
    finally:
        derived.close()
        source_pdf.close()
    atomic_bytes(path, content)
    return content


class EmptyTableRuleInspector:
    """Private composer seam: tables are outside this equation/figure run."""

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


def load_chunk(original: bytes, chunk: int):
    content = make_chunk(original, chunk)
    first = (chunk - 1) * CHUNK_PAGES + 1
    last = min(EXPECTED_PAGES, first + CHUNK_PAGES - 1)
    source = SourceDocument.from_bytes(
        content,
        source_id=f"private:Kittel8ed:pages:{first:04d}-{last:04d}",
        media_type="application/pdf",
        locator=f"private://Kittel8ed/pages-{first:04d}-{last:04d}.pdf",
    )
    extraction = PyMuPdfExtractor(maximum_pages=CHUNK_PAGES).extract(
        source, BytesIO(content)
    )
    document = extraction.document
    filtered_pages = []
    for page in document.pages:
        valid_blocks = tuple(
            block
            for block in page.blocks
            if all(
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
        filtered_pages.append(replace(page, blocks=valid_blocks))
    document = replace(document, pages=tuple(filtered_pages))
    layouts = DeterministicArticleStructureAnalyzer().layout_processor.analyze(
        document
    )
    equation_renderer = PyMuPdfRegionRenderer(
        max_total_pixels=25_000_000,
        max_total_raster_bytes=100_000_000,
    )
    broad_renderer = PyMuPdfRegionRenderer(
        max_total_pixels=100_000_000,
        max_total_raster_bytes=100_000_000,
    )
    equations = DeterministicEquationCandidateDetector(
        region_renderer=equation_renderer
    ).detect_with_layout(document, BytesIO(content), layouts)
    figures = DeterministicFigureCandidateDetector(
        region_renderer=broad_renderer
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
    tables_detected = TableDetectionResult.create(
        detection_input=table_input,
        candidates=(),
        warnings=(),
        processor_name="private-no-table-candidates",
        processor_version="1",
    )
    tables = DeterministicTableStructureReconstructor().reconstruct(
        tables_detected
    )
    structure = DeterministicArticleStructureAnalyzer().analyze(document)
    transcription = DeterministicStructuredTranscriptionComposer().action(
        request=StructuredTranscriptionRequest.create(
            document=document,
            structure_analysis=structure,
            equation_detection_result=equations,
            table_structure_result=tables,
            figure_detection_result=figures,
        )
    )
    return (
        content,
        extraction,
        layouts,
        equations,
        figures,
        tables_detected,
        tables,
        structure,
        transcription,
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
    page_index = candidate.source_spans[0].page_index
    renderer = PyMuPdfRegionRenderer(
        max_total_pixels=25_000_000,
        max_total_raster_bytes=100_000_000,
    )
    return renderer.render(
        source,
        BytesIO(content),
        (PageRegionSelection.for_bounding_box(source, page_index, box),),
    )[0]


def persist_detection(
    chunk: int, data, connection: sqlite3.Connection, elapsed: float
) -> None:
    (
        content,
        extraction,
        layouts,
        equations,
        figures,
        table_detection,
        tables,
        structure,
        transcription,
    ) = data
    directory = chunk_dir(chunk)
    owner_json(directory / "extraction.json", extraction)
    owner_json(directory / "equation-detection.json", equations)
    owner_json(directory / "figure-detection.json", figures)
    owner_json(directory / "table-detection.json", table_detection)
    owner_json(directory / "table-structure.json", tables)
    owner_json(directory / "structure.json", structure)
    owner_json(directory / "structured-transcription.json", transcription)
    start_page = (chunk - 1) * CHUNK_PAGES
    connection.execute("DELETE FROM candidates WHERE chunk_number=?", (chunk,))
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
                "human_label": label,
                "source_page": source_page,
                "owner_candidate": contract_dict(candidate),
                "limitations": [
                    "automated_unreviewed",
                    "candidate_not_validated",
                ],
            },
        )
        connection.execute(
            "INSERT INTO candidates(kind,chunk_number,ordinal,label,source_page,owner_id,state,artifact_path,updated) VALUES('equation',?,?,?,?,?,'detected',?,?)",
            (
                chunk,
                ordinal,
                label,
                source_page,
                candidate.candidate_id,
                str(target.relative_to(ROOT)),
                now(),
            ),
        )
    for ordinal, candidate in enumerate(figures.candidates, 1):
        source_page = start_page + candidate.source_spans[0].page_index + 1
        label = f"Figure p{source_page}-{ordinal}"
        target = directory / "figures" / f"figure-{ordinal:03d}"
        region = figure_region(extraction.document.source, content, candidate)
        atomic_bytes(target / "candidate.png", region.content)
        atomic_json(
            target / "metadata.json",
            {
                "human_label": label,
                "source_page": source_page,
                "owner_candidate": contract_dict(candidate),
                "owner_rendered_region": {
                    k: v
                    for k, v in contract_dict(region).items()
                    if k != "content"
                },
                "associations": [
                    {
                        "role": item.role.value,
                        "text": item.text,
                        "component_id": item.component_id,
                    }
                    for item in candidate.associations
                ],
                "limitations": [
                    "automated_unreviewed",
                    "candidate_not_validated",
                ],
            },
        )
        connection.execute(
            "INSERT INTO candidates(kind,chunk_number,ordinal,label,source_page,owner_id,state,artifact_path,updated) VALUES('figure',?,?,?,?,?,'detected',?,?)",
            (
                chunk,
                ordinal,
                label,
                source_page,
                candidate.candidate_id,
                str(target.relative_to(ROOT)),
                now(),
            ),
        )
    connection.execute(
        "UPDATE chunks SET detection_state='complete',equation_state=?,equation_count=?,figure_count=?,table_count=?,detection_seconds=?,error=NULL,updated=? WHERE chunk_number=?",
        (
            "pending" if equations.candidates else "complete",
            len(equations.candidates),
            len(figures.candidates),
            len(tables.structures),
            elapsed,
            now(),
            chunk,
        ),
    )
    connection.execute(
        "INSERT INTO events(created,label,detail) VALUES(?,?,?)",
        (
            now(),
            f"Pages {start_page + 1}-{start_page + len(extraction.document.pages)}",
            f"Detected {len(equations.candidates)} equations and {len(figures.candidates)} figures in {elapsed:.1f}s",
        ),
    )
    connection.commit()


def status(connection: sqlite3.Connection, phase: str) -> None:
    chunks = {
        row[0]: row[1]
        for row in connection.execute(
            "SELECT detection_state,count(*) FROM chunks GROUP BY detection_state"
        )
    }
    eq_chunks = {
        row[0]: row[1]
        for row in connection.execute(
            "SELECT equation_state,count(*) FROM chunks GROUP BY equation_state"
        )
    }
    candidates = {
        (row[0], row[1]): row[2]
        for row in connection.execute(
            "SELECT kind,state,count(*) FROM candidates GROUP BY kind,state"
        )
    }
    totals = {
        row[0]: row[1]
        for row in connection.execute(
            "SELECT kind,count(*) FROM candidates GROUP BY kind"
        )
    }
    complete_pages = connection.execute(
        "SELECT coalesce(sum(last_page-first_page+1),0) FROM chunks WHERE detection_state='complete'"
    ).fetchone()[0]
    value = {
        "book": "Kittel 8th edition",
        "phase": phase,
        "pages_total": EXPECTED_PAGES,
        "pages_detected": complete_pages,
        "detector_chunks": chunks,
        "equation_chunks": eq_chunks,
        "candidate_totals": totals,
        "candidate_states": {
            f"{kind}_{state}": count
            for (kind, state), count in candidates.items()
        },
        "updated": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "artifacts": {
            "root": str(ROOT),
            "database": "status.sqlite3",
            "transcript": "enriched-transcript.json"
            if FINAL.exists()
            else None,
        },
    }
    atomic_json(PROGRESS, value)
    rows = "".join(
        f"<tr><td>{html.escape(str(key).replace('_', ' ').title())}</td><td>{html.escape(str(val))}</td></tr>"
        for key, val in [
            ("phase", phase),
            ("pages detected", f"{complete_pages} / {EXPECTED_PAGES}"),
            ("equation candidates", totals.get("equation", 0)),
            ("figure candidates", totals.get("figure", 0)),
            ("detector chunks complete", chunks.get("complete", 0)),
            ("equation chunks complete", eq_chunks.get("complete", 0)),
            (
                "figure artifacts retained",
                candidates.get(("figure", "detected_unreviewed"), 0),
            ),
        ]
    )
    document = f"<!doctype html><meta charset='utf-8'><title>Kittel multimodal status</title><style>body{{font:16px system-ui;max-width:760px;margin:2rem auto}}table{{border-collapse:collapse}}td{{border:1px solid #bbb;padding:.5rem 1rem}}</style><h1>Kittel 8th edition</h1><table>{rows}</table><p>Updated {html.escape(value['updated'])}</p>"
    atomic_bytes(STATUS_HTML, document.encode())


def detect_all(connection: sqlite3.Connection, original: bytes) -> None:
    for row in connection.execute(
        "SELECT chunk_number FROM chunks WHERE detection_state!='complete' ORDER BY chunk_number"
    ).fetchall():
        chunk = row[0]
        started = time.monotonic()
        try:
            data = load_chunk(original, chunk)
            persist_detection(
                chunk, data, connection, time.monotonic() - started
            )
        except Exception as error:
            connection.execute(
                "UPDATE chunks SET detection_state='failed',error=?,updated=? WHERE chunk_number=?",
                (f"{type(error).__name__}: {error}", now(), chunk),
            )
            connection.commit()
            status(connection, "detection failed")
            raise
        status(connection, "deterministic detection")


def pix2tex() -> Pix2TexCliEquationRecognizer:
    return Pix2TexCliEquationRecognizer(
        PIX2TEX_EXE,
        backend_version="0.1.4",
        resources=PIX2TEX_RESOURCES,
        timeout_seconds=3600,
    )


def ollama() -> OllamaMultimodalRegionProcessor:
    return OllamaMultimodalRegionProcessor(
        configuration=OllamaMultimodalConfiguration(
            endpoint="http://127.0.0.1:11434",
            model_name=OLLAMA_MODEL,
            expected_model_digest=OLLAMA_DIGEST,
            expected_ollama_version=OLLAMA_VERSION,
            options=OllamaRequestOptions(
                temperature=0.0,
                seed=0,
                context_tokens=8192,
                output_tokens=4096,
                keep_alive="0",
            ),
            limits=OllamaMultimodalLimits(max_selections=1),
            connect_timeout_seconds=5.0,
            read_timeout_seconds=300.0,
        )
    )


def one_assembly(
    artifact: EquationAssemblyArtifact, assembly
) -> EquationAssemblyArtifact:
    artifact_id = stable_id(
        "equation-assembly-artifact",
        EQUATION_ENRICHMENT_CONTRACT_VERSION,
        artifact.source_id,
        artifact.source_content_hash,
        artifact.document_id,
        artifact.detection_result_id,
        (assembly.assembly_id,),
    )
    return EquationAssemblyArtifact(
        artifact_id=artifact_id,
        source_id=artifact.source_id,
        source_content_hash=artifact.source_content_hash,
        document_id=artifact.document_id,
        detection_result_id=artifact.detection_result_id,
        assemblies=(assembly,),
    )


def smoke(connection: sqlite3.Connection, original: bytes) -> None:
    eq = connection.execute(
        "SELECT * FROM candidates WHERE kind='equation' ORDER BY source_page,ordinal LIMIT 1"
    ).fetchone()
    fig = connection.execute(
        "SELECT * FROM candidates WHERE kind='figure' ORDER BY source_page,ordinal LIMIT 1"
    ).fetchone()
    if eq is None or fig is None:
        raise RuntimeError(
            "deterministic inventory did not yield both candidate kinds"
        )
    durations: dict[str, float] = {}
    chunk = eq["chunk_number"]
    data = load_chunk(original, chunk)
    content, extraction, _layouts, equations, *_rest = data
    assembly_artifact = DeterministicEquationAssembler(
        renderer=PyMuPdfRegionRenderer()
    ).assemble(equations, content)
    candidate_id = eq["owner_id"]
    assembly = next(
        item
        for item in assembly_artifact.assemblies
        if candidate_id in item.candidate_ids
    )
    selected = one_assembly(assembly_artifact, assembly)
    started = time.monotonic()
    recognition = pix2tex().process(selected)
    durations["pix2tex_seconds"] = time.monotonic() - started
    target = ROOT / "smoke" / "equation"
    atomic_bytes(target / "evidence.png", assembly.rendered_region.content)
    owner_json(target / "assembly.json", selected)
    owner_json(target / "recognition.json", recognition)

    chunk = fig["chunk_number"]
    data = load_chunk(original, chunk)
    content, extraction, _layouts, _equations, figures, *_rest = data
    candidate = figures.candidates[fig["ordinal"] - 1]
    region = figure_region(extraction.document.source, content, candidate)
    request = OllamaMultimodalRegionProcessingRequest.create(
        (OllamaMultimodalSelection.from_rendered_region(region),)
    )
    started = time.monotonic()
    result = ollama().action(request=request)
    durations["ollama_seconds"] = time.monotonic() - started
    target = ROOT / "smoke" / "figure"
    atomic_bytes(target / "evidence.png", region.content)
    owner_json(target / "proposal.json", result)
    if not result.cacheable:
        raise RuntimeError(
            "Ollama figure smoke did not produce a complete cacheable result"
        )
    atomic_json(
        ROOT / "smoke" / "summary.json",
        {
            "status": "succeeded",
            "equation_label": eq["label"],
            "figure_label": fig["label"],
            **durations,
            "limitations": ["automated_unreviewed", "proposals_not_accepted"],
        },
    )
    connection.execute(
        "INSERT INTO events(created,label,detail) VALUES(?,?,?)",
        (
            now(),
            "Candidate smoke",
            f"Pix2Tex {durations['pix2tex_seconds']:.1f}s; Ollama {durations['ollama_seconds']:.1f}s",
        ),
    )
    connection.commit()
    status(connection, "smoke succeeded")


def enrich_equations(connection: sqlite3.Connection, original: bytes) -> None:
    recognizer = pix2tex()
    rows = connection.execute(
        "SELECT chunk_number FROM chunks WHERE equation_count>0 AND equation_state!='complete' ORDER BY chunk_number"
    ).fetchall()
    for row in rows:
        chunk = row[0]
        started = time.monotonic()
        try:
            data = load_chunk(original, chunk)
            content, _extraction, _layouts, equations, *_rest = data
            assembly = DeterministicEquationAssembler(
                renderer=PyMuPdfRegionRenderer()
            ).assemble(equations, content)
            recognition_request = EquationRecognitionRequest.create(
                assembly_artifact=assembly,
                processor_identity=recognizer.identity,
            )
            recognition = recognizer.action(request=recognition_request)
            index = build_equation_index(assembly, recognition)
            target = chunk_dir(chunk) / "equation-enrichment"
            owner_json(target / "assembly.json", assembly)
            owner_json(target / "recognition.json", recognition)
            owner_json(target / "index.json", index)
            for ordinal, item in enumerate(assembly.assemblies, 1):
                atomic_bytes(
                    target / f"assembly-{ordinal:03d}.png",
                    item.rendered_region.content,
                )
            elapsed = time.monotonic() - started
            connection.execute(
                "UPDATE chunks SET equation_state='complete',equation_seconds=?,error=NULL,updated=? WHERE chunk_number=?",
                (elapsed, now(), chunk),
            )
            connection.execute(
                "UPDATE candidates SET state='complete',runtime_seconds=?,error=NULL,updated=? WHERE kind='equation' AND chunk_number=?",
                (elapsed, now(), chunk),
            )
            connection.commit()
        except Exception as error:
            connection.execute(
                "UPDATE chunks SET equation_state='failed',error=?,updated=? WHERE chunk_number=?",
                (f"{type(error).__name__}: {error}", now(), chunk),
            )
            connection.commit()
            status(connection, "equation enrichment failed")
            raise
        status(connection, "equation enrichment")


def enrich_figures(connection: sqlite3.Connection, original: bytes) -> None:
    del original
    connection.execute(
        "UPDATE candidates SET state='detected_unreviewed',runtime_seconds=0,error=NULL,updated=? WHERE kind='figure'",
        (now(),),
    )
    connection.execute(
        "INSERT INTO events(created,label,detail) VALUES(?,?,?)",
        (
            now(),
            "Figure artifacts retained",
            "Bulk model calls skipped; deterministic images and source associations retained",
        ),
    )
    connection.commit()
    status(connection, "deterministic figure artifacts retained")


def publish_final(
    connection: sqlite3.Connection, baseline: dict[str, object]
) -> None:
    incomplete_eq = connection.execute(
        "SELECT count(*) FROM chunks WHERE equation_count>0 AND equation_state!='complete'"
    ).fetchone()[0]
    incomplete_fig = connection.execute(
        "SELECT count(*) FROM candidates WHERE kind='figure' AND state!='detected_unreviewed'"
    ).fetchone()[0]
    if incomplete_eq or incomplete_fig:
        raise RuntimeError("enrichment tasks remain incomplete")
    pages = []
    for page in baseline["pages"]:
        pages.append(
            {
                "page_number": page["page_index"] + 1,
                "printed_page_label": page.get("printed_page_label"),
                "composed_text": page["text"],
                "composed_text_source": page["chosen_source"],
                "structured_items": [],
                "equations": [],
                "figures": [],
            }
        )
    equation_counts = {
        "primary": 0,
        "auxiliary": 0,
        "rejected": 0,
        "failed": 0,
        "not_requested": 0,
    }
    figure_counts = {
        "detected": 0,
        "with_associations": 0,
        "with_captions": 0,
        "without_captions": 0,
    }
    for chunk in range(1, EXPECTED_PAGES // CHUNK_PAGES + 1):
        offset = (chunk - 1) * CHUNK_PAGES
        transcription = json.loads(
            (chunk_dir(chunk) / "structured-transcription.json").read_text()
        )
        for item in transcription["items"]:
            page_number = offset + item["page_index"] + 1
            pages[page_number - 1]["structured_items"].append(item)
        index_path = chunk_dir(chunk) / "equation-enrichment/index.json"
        if index_path.exists():
            index = json.loads(index_path.read_text())
            recognition = json.loads(
                (
                    chunk_dir(chunk) / "equation-enrichment/recognition.json"
                ).read_text()
            )
            recognition_by_assembly = {
                proposal["assembly_id"]: proposal
                for proposal in recognition["proposals"]
            }
            for proposal in recognition["proposals"]:
                if proposal["status"] == "failed":
                    equation_counts["failed"] += 1
                elif proposal["status"] == "not_requested":
                    equation_counts["not_requested"] += 1
            for ordinal, record in enumerate(index["records"], 1):
                tier = record["tier"]
                equation_counts[tier] += 1
                proposal = recognition_by_assembly[record["assembly_id"]]
                if tier != "primary" or proposal["status"] != "proposed":
                    continue
                page_number = offset + record["page_index"] + 1
                pages[page_number - 1]["equations"].append(
                    {
                        "evidence_path": (
                            f"chunks/chunk-{chunk:03d}/equation-enrichment/"
                            f"assembly-{ordinal:03d}.png"
                        ),
                        "owner_index_record": record,
                    }
                )
        for row in connection.execute(
            "SELECT artifact_path,source_page,label FROM candidates WHERE kind='figure' AND chunk_number=? ORDER BY ordinal",
            (chunk,),
        ):
            metadata = json.loads(
                (ROOT / row["artifact_path"] / "metadata.json").read_text()
            )
            associations = metadata["associations"]
            has_caption = any(
                item["role"] == "caption" for item in associations
            )
            figure_counts["detected"] += 1
            figure_counts["with_associations"] += int(bool(associations))
            figure_counts["with_captions"] += int(has_caption)
            figure_counts["without_captions"] += int(not has_caption)
            pages[row["source_page"] - 1]["figures"].append(
                {
                    "label": row["label"],
                    "png_path": f"{row['artifact_path']}/candidate.png",
                    "caption_status": "associated"
                    if has_caption
                    else "detected_unreviewed_without_caption",
                    "associations": associations,
                    "owner_candidate": metadata["owner_candidate"],
                    "owner_rendered_region": metadata["owner_rendered_region"],
                }
            )
    value = {
        "schema_version": 1,
        "book": "Kittel 8th edition",
        "status": "automated_unreviewed",
        "page_count": EXPECTED_PAGES,
        "equation_counts": equation_counts,
        "figure_counts": figure_counts,
        "composition_policy": "page_ordered_baseline_text_plus_owner_structured_items_primary_equations_and_deterministic_figure_artifacts",
        "limitations": [
            "automated_unreviewed",
            "not_human_proofread",
            "equation_proposals_not_accepted",
            "figure_candidates_not_semantically_described",
            "bulk_figure_model_calls_skipped",
            "single_figure_smoke_proposal_retained_as_evidence_only_outside_transcript",
            "derived_ten_page_detection_sources_retain_original_page_mapping",
            "out_of_page_extraction_geometry_is_omitted_from_typed_detection_but_retained_in_raw_extraction_and_baseline_text",
        ],
        "pages": pages,
    }
    atomic_json(FINAL, value)
    connection.execute(
        "INSERT INTO events(created,label,detail) VALUES(?,?,?)",
        (
            now(),
            "Transcript published",
            "700 page enriched transcript complete",
        ),
    )
    connection.commit()
    status(connection, "complete")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("detect", "smoke", "run", "status"))
    arguments = parser.parse_args()
    os.umask(0o077)
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_stream = LOCK.open("a+b")
    try:
        fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("another Kittel multimodal run holds the lock", file=sys.stderr)
        return 4
    connection = connect()
    try:
        original, baseline = check_inputs()
        if arguments.phase == "status":
            status(connection, "status")
            return 0
        if arguments.phase == "detect":
            detect_all(connection, original)
            status(connection, "detection complete")
            return 0
        if arguments.phase == "smoke":
            detect_all(connection, original)
            smoke(connection, original)
            return 0
        detect_all(connection, original)
        enrich_equations(connection, original)
        enrich_figures(connection, original)
        publish_final(connection, baseline)
        return 0
    except Exception:
        traceback.print_exc()
        return 1
    finally:
        connection.close()
        lock_stream.close()


if __name__ == "__main__":
    raise SystemExit(main())
