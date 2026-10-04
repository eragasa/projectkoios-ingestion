# Ingestion v0 Implementation

## Source Layout

### Shared pilot contracts

| Class | Implementation |
|---|---|
| `BaseDocument` | [`base.py`](../../../../src/python/projectkoios/ingestion/base.py) |
| `BaseProcessedDocument` | [`base.py`](../../../../src/python/projectkoios/ingestion/base.py) |
| `BaseProcessedDocumentChunk` | [`base.py`](../../../../src/python/projectkoios/ingestion/base.py) |
| `BaseProcessedDocumentChunks` | [`base.py`](../../../../src/python/projectkoios/ingestion/base.py) |
| `BaseDocumentProcessor` | [`base.py`](../../../../src/python/projectkoios/ingestion/base.py) |
| `BaseIngestor` | [`base.py`](../../../../src/python/projectkoios/ingestion/base.py) |
| `BaseProcessedDocumentChunker` | [`base.py`](../../../../src/python/projectkoios/ingestion/base.py) |
| `BaseRAG` | [`base.py`](../../../../src/python/projectkoios/ingestion/base.py) |

### BibTeX facade

| Class | Implementation | Focused validation |
|---|---|---|
| `BibTexRecord` | [`bibtex.py`](../../../../src/python/projectkoios/ingestion/bibtex.py) | [`test_BibtexParser.py`](../../../../tests/bibtex/test_BibtexParser.py) |
| `BibtexParser` | [`bibtex.py`](../../../../src/python/projectkoios/ingestion/bibtex.py) | [`test_BibtexParser.py`](../../../../tests/bibtex/test_BibtexParser.py) |
| `BibtexReferenceError` | [`bibtex.py`](../../../../src/python/projectkoios/ingestion/bibtex.py) | [`test_BaseDocument.py`](../../../../tests/base/test_BaseDocument.py) and [`test_BibtexParser.py`](../../../../tests/bibtex/test_BibtexParser.py) |

### PDF processing

| Class | Implementation | Focused validation |
|---|---|---|
| `PdfProcessedPage` | [`documents/pdf.py`](../../../../src/python/projectkoios/ingestion/documents/pdf.py) | [`test_PdfDocumentProcessor.py`](../../../../tests/documents/pdf/test_PdfDocumentProcessor.py) |
| `PdfProcessedDocument` | [`documents/pdf.py`](../../../../src/python/projectkoios/ingestion/documents/pdf.py) | [`test_PdfDocumentProcessor.py`](../../../../tests/documents/pdf/test_PdfDocumentProcessor.py) |
| `PdfDocumentProcessor` | [`documents/pdf.py`](../../../../src/python/projectkoios/ingestion/documents/pdf.py) | [`test_PdfDocumentProcessor.py`](../../../../tests/documents/pdf/test_PdfDocumentProcessor.py) |

`PdfDocumentProcessor` translates the pilot document to the existing
`SourceDocument`, calls
[`PyMuPdfExtractor`](../../../../src/python/projectkoios/ingestion/pdf/adapters/pymupdf/extraction.py),
and projects the extraction result to page text. The concrete PyMuPDF adapter
continues to own rich extraction evidence.

### Pilot composition

| Class | Implementation | Focused validation |
|---|---|---|
| `PilotDocument` | [`pilot/models.py`](../../../../src/python/projectkoios/ingestion/pilot/models.py) | [`test_PilotDocument.py`](../../../../tests/pilot/models/test_PilotDocument.py) |
| `PilotIngestor` | [`pilot/ingestor.py`](../../../../src/python/projectkoios/ingestion/pilot/ingestor.py) | [`test_PilotIngestor.py`](../../../../tests/pilot/ingestor/test_PilotIngestor.py) |
| `PilotProcessedDocumentChunker` | [`pilot/chunker.py`](../../../../src/python/projectkoios/ingestion/pilot/chunker.py) | [`test_PilotProcessedDocumentChunker.py`](../../../../tests/pilot/chunker/test_PilotProcessedDocumentChunker.py) |
| `PilotRAG` | [`pilot/rag.py`](../../../../src/python/projectkoios/ingestion/pilot/rag.py) | [`test_PilotRAG.py`](../../../../tests/pilot/rag/test_PilotRAG.py) |
| `PilotIngestionPipeline` | [`pilot/pipeline.py`](../../../../src/python/projectkoios/ingestion/pilot/pipeline.py) | [`test_PilotIngestionPipeline.py`](../../../../tests/pilot/pipeline/test_PilotIngestionPipeline.py) |

The [`pilot` package API](../../../../src/python/projectkoios/ingestion/pilot/__init__.py)
re-exports only the deliberate pilot composition surface. PDF processing types
remain public through their implementation module rather than being aliased
through the pilot package.

## Implemented Behavior

### Citation-first document construction

`BaseDocument` contains a `BibTexRecord`, locator, media type, and exact content
bytes. Its constructor raises `BibtexReferenceError` when `source_id` is not a
`BibTexRecord`. `PilotDocument` is the concrete frozen subclass used by the
pilot.

`BibtexParser.parse(content, citation_key)` lazily imports Pybtex, parses the
supplied BibTeX text, selects the requested key, and returns the project-owned
immutable record. A missing key raises `BibtexReferenceError`. The current
projection retains the citation key, entry type, and sorted ordinary fields;
Pybtex objects do not leave `bibtex.py`.

### PDF processing

`PdfDocumentProcessor.process(document)` rejects media types other than
`application/pdf`. It creates the existing `SourceDocument` from exact bytes,
the citation key, locator, and media type, then calls its configured
`PyMuPdfExtractor` with an in-memory stream.

Each extracted physical page becomes a `PdfProcessedPage` containing its zero-
based page index, optional printed page label, and newline-joined native text
blocks. The ordered pages and original `BaseDocument` form a
`PdfProcessedDocument`. The complete extraction result remains available to the
established evidence pipeline but is not retained by this pilot projection.

`PilotIngestor` does not import or construct PyMuPDF. It accepts any
`BaseDocumentProcessor` and returns the processor result unchanged.

### Chunking and answering

`PilotProcessedDocumentChunker` requires `PdfProcessedDocument` and a positive
`max_characters`. It walks pages in order, slices each non-empty page into fixed-
size character ranges, and creates `BaseProcessedDocumentChunk` values carrying
page index and text. It performs no tokenization, overlap, semantic splitting,
or embedding.

`PilotIngestionPipeline.ingest()` calls the configured ingestor and chunker,
stores the resulting `BaseProcessedDocumentChunks`, and returns that same
object. `PilotRAG.answer()` remains separate: it computes case-folded
whitespace-token overlap and returns the first highest-scoring chunk text, or an
empty string when no chunks exist. It currently performs retrieval rather than
generation.

## Established v0 Components

The pilot is additive. Existing implementation areas remain:

| Area | Implementation |
|---|---|
| Shared extraction models | [`models.py`](../../../../src/python/projectkoios/ingestion/models.py) |
| Injected component boundaries | Nominal abstract bases in their owning domain modules |
| PDF extraction and rendering | [`pdf/`](../../../../src/python/projectkoios/ingestion/pdf/) |
| Article ingestion | [`articles/`](../../../../src/python/projectkoios/ingestion/articles/) |
| Textbook ingestion | [`textbooks/`](../../../../src/python/projectkoios/ingestion/textbooks/) |
| Bounded processing | Retired; concrete processing stages own their request/result boundaries |
| Deterministic derivations | [Deterministic implementation map](deterministic/implementation.md) |
| Provenance audit | [`provenance/`](../../../../src/python/projectkoios/ingestion/provenance/) |
| Batch entry points | [`batch_cli.py`](../../../../src/python/projectkoios/ingestion/batch_cli.py) and transcript batch modules |

## Runtime and Dependency Boundaries

- `pybtex` is provided by the optional `bibtex` dependency group and the `dev`
  group. It is imported lazily by `BibtexParser`.
- `PyMuPDF` is provided by the optional `pdf` dependency group and the `dev`
  group. Pilot code reaches it only through `PdfDocumentProcessor` and the
  existing PDF adapter.
- The pilot reads exact PDF bytes in memory.
- Pilot data classes are immutable; `PilotIngestionPipeline.chunks` is the one
  explicit mutable last-run value.
- The pilot writes no artifacts and chooses no search or vector backend.

## Deferred Pilot Limits

The implementation intentionally defers:

- a non-bibliographic `BaseDocument` identity until a supported source cannot
  supply a citation record;
- exact block, geometry, warning, and source-span retention in pilot chunks
  until evidence-grounded citation or provenance-complete retrieval is claimed;
- exact BibTeX entry and person retention until bibliography data is
  authoritative, user-visible, or exportable;
- immutable per-run pipeline results until concurrent, asynchronous, or
  multi-document operation; and
- renaming `PilotRAG` or adding generation until a user-facing RAG claim.

The evidence, consequences, and revisit conditions are recorded as
`INGESTION-PILOT-001` through `INGESTION-PILOT-005` in
`projectkoios/docs/development/software-review.md`.

## Test Organization

Pilot tests mirror the implementation package and class:

```text
tests/base/test_BaseDocument.py
tests/bibtex/test_BibtexParser.py
tests/documents/pdf/test_PdfDocumentProcessor.py
tests/pilot/models/test_PilotDocument.py
tests/pilot/ingestor/test_PilotIngestor.py
tests/pilot/chunker/test_PilotProcessedDocumentChunker.py
tests/pilot/rag/test_PilotRAG.py
tests/pilot/pipeline/test_PilotIngestionPipeline.py
```

The maintained pilot resources are:

```text
tests/resources/pilot/pilot-document.bib
tests/resources/pilot/pilot-document.pdf
```

## Validation

From the repository root, run:

```bash
PYTHONPATH=.:src/python pytest -q tests/base tests/bibtex \
  tests/documents/pdf tests/pilot
ruff check src/python/projectkoios/ingestion/base.py \
  src/python/projectkoios/ingestion/bibtex.py \
  src/python/projectkoios/ingestion/documents \
  src/python/projectkoios/ingestion/pilot \
  tests/base tests/bibtex tests/documents/pdf tests/pilot
ruff format --check src/python/projectkoios/ingestion/base.py \
  src/python/projectkoios/ingestion/bibtex.py \
  src/python/projectkoios/ingestion/documents \
  src/python/projectkoios/ingestion/pilot \
  tests/base tests/bibtex tests/documents/pdf tests/pilot
PYTHONPATH=src/python mypy \
  src/python/projectkoios/ingestion/base.py \
  src/python/projectkoios/ingestion/bibtex.py \
  src/python/projectkoios/ingestion/documents \
  src/python/projectkoios/ingestion/pilot
PYTHONPATH=.:src/python pytest -q
```

See [architecture.md](architecture.md) for the governing boundaries and
[index.md](index.md) for the concise system view.
