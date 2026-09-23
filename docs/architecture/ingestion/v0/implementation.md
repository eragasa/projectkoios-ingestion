# Ingestion v0 Implementation

## Source Layout

### Shared pilot contracts

| Class | Implementation |
|---|---|
| `BaseDocument` | [`base.py`](../../../../src/python/projectkoios/ingestion/base.py) |
| `BaseProcessedDocument` | [`base.py`](../../../../src/python/projectkoios/ingestion/base.py) |
| `BaseProcessedPage` | [`base.py`](../../../../src/python/projectkoios/ingestion/base.py) |
| `BaseProcessedDocumentChunk` | [`base.py`](../../../../src/python/projectkoios/ingestion/base.py) |
| `BaseProcessedDocumentChunks` | [`base.py`](../../../../src/python/projectkoios/ingestion/base.py) |
| `BaseDocumentProcessor` | [`base.py`](../../../../src/python/projectkoios/ingestion/base.py) |
| `BaseIngestor` | [`base.py`](../../../../src/python/projectkoios/ingestion/base.py) |
| `BaseProcessedDocumentChunker` | [`base.py`](../../../../src/python/projectkoios/ingestion/base.py) |
| `BaseRAG` | [`base.py`](../../../../src/python/projectkoios/ingestion/base.py) |

### Planned iteration-two contracts

The following design contracts are not implemented yet:

| Class | Planned responsibility |
|---|---|
| `BaseDocumentPersister` | Validate and serialize one exact source document through an injected store. |
| `BaseDocumentPersistanceStore` | Retain and resolve exact original BibTeX and PDF source bytes and locations. |
| `BaseProcessedDocumentPersister` | Validate and serialize one processed-document contract through an injected store. |
| `BaseProcessedDocumentPersistanceStore` | Retain and resolve canonical `extraction.json` bytes and locations. |
| `BaseDeterministicProcessor` | Define the ordered deterministic composition contract. |
| `DeterministicProcessor` | Execute a validated prefix of the deterministic component order. |
| `PilotDeterministicProcessor` | Encapsulate one verified `PdfProcessedDocument` for pilot composition. |

These names describe the planned iteration-two direction in
[architecture.md](architecture.md); their source and focused tests will be added
only with their implementation slices.

### BibTeX facade

| Class | Implementation | Focused validation |
|---|---|---|
| `BibTexRecord` | [`bibtex.py`](../../../../src/python/projectkoios/ingestion/bibtex.py) | [`test_BibtexParser.py`](../../../../tests/bibtex/test_BibtexParser.py) |
| `BibtexParser` | [`bibtex.py`](../../../../src/python/projectkoios/ingestion/bibtex.py) | [`test_BibtexParser.py`](../../../../tests/bibtex/test_BibtexParser.py) |
| `BibtexReferenceError` | [`bibtex.py`](../../../../src/python/projectkoios/ingestion/bibtex.py) | [`test_BaseDocument.py`](../../../../tests/base/test_BaseDocument.py) and [`test_BibtexParser.py`](../../../../tests/bibtex/test_BibtexParser.py) |

### PDF processing and corpus loading

| Class | Implementation | Focused validation |
|---|---|---|
| `ProcessedPdfPage` | [`documents/pdf.py`](../../../../src/python/projectkoios/ingestion/documents/pdf.py) | [`test_PdfDocumentProcessor.py`](../../../../tests/documents/pdf/test_PdfDocumentProcessor.py) |
| `PdfProcessedDocument` | [`documents/pdf.py`](../../../../src/python/projectkoios/ingestion/documents/pdf.py) | [`test_PdfDocumentProcessor.py`](../../../../tests/documents/pdf/test_PdfDocumentProcessor.py) |
| `PdfProcessedDocuments` | [`documents/pdf.py`](../../../../src/python/projectkoios/ingestion/documents/pdf.py) | [`test_ProcessedPdfDocumentsDeserializer.py`](../../../../tests/documents/pdf/test_ProcessedPdfDocumentsDeserializer.py) |
| `PdfDocumentProcessor` | [`documents/pdf.py`](../../../../src/python/projectkoios/ingestion/documents/pdf.py) | [`test_PdfDocumentProcessor.py`](../../../../tests/documents/pdf/test_PdfDocumentProcessor.py) |
| `ProcessedPdfDocumentDeserializer` | [`documents/pdf.py`](../../../../src/python/projectkoios/ingestion/documents/pdf.py) | [`test_ProcessedPdfDocumentDeserializer.py`](../../../../tests/documents/pdf/test_ProcessedPdfDocumentDeserializer.py) |
| `ProcessedPdfDocumentsDeserializer` | [`documents/pdf.py`](../../../../src/python/projectkoios/ingestion/documents/pdf.py) | [`test_ProcessedPdfDocumentsDeserializer.py`](../../../../tests/documents/pdf/test_ProcessedPdfDocumentsDeserializer.py) |

`PdfDocumentProcessor` translates the pilot document to the existing
`SourceDocument`, calls
[`PyMuPdfExtractor`](../../../../src/python/projectkoios/ingestion/pdf/extractor.py),
and projects the extraction result to page text while retaining the validated
`ExtractionResult`. The existing extractor remains the PyMuPDF adapter and
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

Each extracted physical page becomes a
`ProcessedPdfPage(BaseProcessedPage)` containing its zero-based page index,
newline-joined native text, and optional PDF printed-page label. The ordered
pages, original `BaseDocument`, and exact validated
`ExtractionResult` form a `PdfProcessedDocument`. Manually constructed test or
adapter values may omit extraction evidence, but deterministic corpus processing
must use retained extraction evidence.

### Corpus deserialization

One processed-document manifest contains an ordered non-empty list of explicit
`citation_key`, `bibtex_path`, `pdf_path`, and `processed_document_path`
locations. All paths are normalized relative paths resolved beneath the
manifest directory. The processed-document path names the existing canonical
`extraction.json` artifact rather than a second serialization containing copied
PDF bytes.

`ProcessedPdfDocumentDeserializer` reads one explicit location triple, selects
the citation key from the BibTeX source, reads the exact PDF bytes, strictly
deserializes and validates the extraction artifact, and requires its logical
source identity, media type, byte length, and SHA-256 identity to match the PDF.
It then constructs the retained `PdfProcessedDocument` projection.
`ProcessedPdfDocumentsDeserializer` preserves manifest order, rejects duplicate
citation keys, PDF paths, and extraction paths, and returns
`PdfProcessedDocuments`. Neither deserializer scans directories or infers
relationships from filenames.

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
| Existing component protocols | [`protocols.py`](../../../../src/python/projectkoios/ingestion/protocols.py) |
| PDF extraction and rendering | [`pdf/`](../../../../src/python/projectkoios/ingestion/pdf/) |
| Article ingestion | [`articles/`](../../../../src/python/projectkoios/ingestion/articles/) |
| Textbook ingestion | [`textbooks/`](../../../../src/python/projectkoios/ingestion/textbooks/) |
| Bounded processing | [`processing.py`](../../../../src/python/projectkoios/ingestion/processing.py) |
| Deterministic derivations | [Deterministic implementation map](deterministic/implementation.md) |
| Provenance audit | [`provenance.py`](../../../../src/python/projectkoios/ingestion/provenance.py) |
| Batch entry points | [`batch_cli.py`](../../../../src/python/projectkoios/ingestion/batch_cli.py) and transcript batch modules |

## Runtime and Dependency Boundaries

- `pybtex` is provided by the optional `bibtex` dependency group and the `dev`
  group. It is imported lazily by `BibtexParser`.
- `PyMuPDF` is provided by the optional `pdf` dependency group and the `dev`
  group. Pilot code reaches it only through `PdfDocumentProcessor` and the
  existing PDF adapter.
- The pilot reads exact PDF bytes in memory.
- Corpus deserialization has explicit limits for manifest, BibTeX, PDF,
  extraction-artifact, and item counts; callers may lower per-document byte
  limits.
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

These conditions bound the pilot implementation; they do not establish a
durable cross-repository architecture decision. Any such decision remains owned
by `projectkoios`.

## Test Organization

Pilot tests mirror the implementation package and class:

```text
tests/base/test_BaseDocument.py
tests/base/test_BaseProcessedPage.py
tests/bibtex/test_BibtexParser.py
tests/documents/pdf/test_PdfDocumentProcessor.py
tests/documents/pdf/test_ProcessedPdfDocumentDeserializer.py
tests/documents/pdf/test_ProcessedPdfDocumentsDeserializer.py
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
