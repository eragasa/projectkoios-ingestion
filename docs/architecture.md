# Project Koios Ingestion Architecture

## Purpose

`projectkoios-ingestion` is the source-ingestion and document-processing
boundary for Project Koios. It converts source-specific inputs into explicit,
inspectable, destination-independent objects and coordinates their delivery to
consumer-provided interfaces.

The package is reusable software. Source locations, naming conventions,
bibliography policies, note templates, and destination layouts are supplied by
applications or deployment configuration.

## Scope

The repository owns:

- coordination of source loading and document processing;
- source-specific ingestion implementations;
- normalized extraction and structure models owned by ingestion;
- provenance captured during extraction and transformation;
- confidence and warning records for uncertain extraction;
- content-addressed extraction identity and cache contracts;
- coordination with consumer-provided chunk producers and writers.

The repository does not own:

- full-text, vector, or graph search storage;
- retrieval, ranking, or context assembly;
- bibliography mutation or citation-key policy;
- Obsidian or other destination-specific rendering;
- vault writes or human-note promotion;
- user-specific source paths, names, or templates;
- workflow-engine semantics or model-provider implementations.

## Current Architecture

The implemented code-repository pipeline is:

```text
CodeRepository
    -> CodeRepositoryLoader
    -> CodeRepositoryIngester
    -> LineChunker
    -> TextChunk stream
    -> ChunkIndexWriter
```

`CodeRepositoryIngester` coordinates a loader and chunker.
`CodeRepositoryIndexer` sends the resulting stream to a consumer-provided
`ChunkIndexWriter`. Chunking algorithms, repository loading, and concrete
indices remain dependencies outside this repository as established by
`adr.20260629.establish-ingestion-repo.md`.

## Planned Document Processing Model

PDF document support follows an output-independent pipeline:

```text
SourceDocument
    -> SourceExtractor
    -> ExtractedDocument
    -> StructuralAnalyzer
    -> StructuredDocument
    -> optional ChunkProducer
    -> IngestionResult
```

An article or textbook ingester specializes extraction and structural analysis
without selecting a destination:

```text
PdfArticleIngester.ingest(...) -> ExtractedArticle
PdfTextbookIngester.ingest(...) -> ExtractedTextbook
```

Markdown notes, search records, and other projections are downstream views of
these objects. They are not PDF-ingestion return types.

## Cold and Just-in-Time Processing

The architecture separates inexpensive, reusable cold processing from
expensive just-in-time processing.

### Cold processing

Cold processing may capture:

- logical source identity and exact source-blob hash;
- PDF metadata and page labels;
- bookmarks and table-of-contents candidates;
- page text blocks, reading order, and coordinates;
- font and layout information;
- image references and bounding boxes;
- equation, figure, example, and problem candidates;
- extraction quality and warnings.

Cold results are reusable by every downstream destination. Unchanged sources
must not be re-extracted when a compatible cached result exists.

### Just-in-time processing

An application may request enrichment of a selected page range or structural
unit. JIT work can include OCR, page-region rendering, expensive structural
analysis, or semantic cleanup through injected processors.

The ingestion package defines and coordinates the request and result contracts.
It does not choose when retrieval should trigger the request, which model to
run, or where a projected artifact should be written.

JIT cache identity includes at least:

```text
logical source ID
+ exact source-blob hash
+ selected source spans
+ extractor version
+ processor version
+ processor configuration digest
```

A processor change invalidates its derived result without invalidating the raw
extraction.

## Structural Model

A structured document is a hierarchy whose nodes refer to source spans:

```text
Document
    -> FrontMatter
    -> Chapter
        -> Section
            -> Subsection
            -> Prose
            -> Equation
            -> Figure
            -> Example
        -> ProblemSet
            -> Problem
```

The hierarchy is descriptive rather than destination-specific. Node labels
preserve source labels as strings. File naming, zero padding, citekeys, and
Markdown conventions are projection policies outside ingestion.

Structure detection uses evidence in descending order of reliability:

1. explicit PDF bookmarks;
2. a parsed table of contents;
3. numbered heading patterns;
4. font and layout hierarchy;
5. bounded page-range fallback.

Every inferred node records its evidence, confidence, and warnings. Consumers
must be able to inspect or override uncertain structure without re-reading the
source PDF.

## Rough Chunking Boundary

The accepted repository boundary places chunking algorithms outside this
repository. Ingestion may coordinate an injected `ChunkProducer`, but it does
not define search-specific chunk sizes, overlap, embedding behavior, or ranking
semantics.

A chunk accepted or emitted at the ingestion boundary must preserve:

- stable logical source identity and exact source-blob identity;
- ordered source spans;
- structural ancestry where known;
- content kind;
- neighboring and parent relationships where supplied;
- extraction confidence and warnings.

Moving a concrete textbook chunking algorithm into this repository requires an
ADR that explicitly supersedes the existing boundary.

## Provenance

Every extracted textual or visual object must resolve to:

- logical source identity, exact source-blob identity, and content hash;
- physical PDF page index;
- printed page label when available;
- source block or object identifier;
- bounding box when available;
- extractor and processor versions.

Transformations are append-only derivations. Cleaned content points to raw
extracted content; it does not replace it. Provenance must remain representable
without Markdown, Obsidian links, or a particular database.

Logical source identity is supplied independently of source bytes. Exact blob,
block, and extraction identities derive from the source-blob hash and
source-local evidence, not from global list positions. Adding an earlier chunk
or structure node must not renumber unrelated objects.

## Artifact Ownership

Machine-generated extraction artifacts are reproducible and replaceable.
Human-authored artifacts are outside this repository and must never be treated
as regeneration targets.

The ingestion package may return bytes, objects, iterators, manifests, or
artifact descriptions. Writing them to a filesystem or vault requires an
explicit consumer-provided writer.

## Extension Protocols

The planned architecture depends on small protocols:

- `SourceExtractor` converts a source into normalized extraction objects;
- `StructuralAnalyzer` proposes a source-backed document hierarchy;
- `DocumentProcessor` derives enriched content while preserving provenance;
- `ChunkProducer` converts structured content into source-backed chunks;
- `ExtractionCache` retrieves and stores versioned extraction results;
- `ArtifactWriter` accepts destination-neutral artifacts;
- `ChunkIndexWriter` accepts chunk streams.

Concrete implementations depend inward on these contracts. Optional PDF,
OCR, or model dependencies must not be imported merely by importing the base
package.

## Dependency Rules

1. Domain models do not import PDF, search, model-provider, or vault libraries.
2. PDF libraries are confined to PDF adapters.
3. Search implementations depend on ingestion contracts, not the reverse.
4. Destination renderers depend on ingestion results, not the reverse.
5. External boundary models may validate serialized input, while internal
   models prefer dataclasses or ordinary classes.
6. Optional dependencies are loaded only when their adapter is used.

## Failure and Confidence Model

Extraction does not silently discard uncertainty. A result may contain usable
content and warnings at the same time.

Warnings identify at least:

- missing or contradictory page labels;
- uncertain reading order;
- low text density or likely scan pages;
- probable OCR requirement;
- ambiguous heading level;
- uncertain equation or figure association;
- malformed source metadata;
- unsupported or encrypted input.

Fatal errors prevent creation of a valid result. Recoverable uncertainty is
represented in the result manifest.

## Idempotency

Given the same source bytes, extractor version, and configuration, deterministic
extraction must produce equivalent normalized content and stable identifiers.

Cache writes and downstream delivery must be retryable. This repository does
not assume that a consumer supports destructive replacement.

## Package Direction

The intended package shape is:

```text
projectkoios/ingestion/
    models.py
    protocols.py
    provenance.py
    articles/
        base.py
        pdf.py
    textbooks/
        base.py
        pdf.py
        structure.py
    pdf/
        extractor.py
        models.py
        quality.py
```

This is a direction, not a claim that all modules are implemented. Public
exports are added only with tested behavior and documented contracts.

## Testing Strategy

Tests use generated or redistributable fixtures rather than private document
collections. They verify:

- deterministic output and stable IDs;
- exact page and bounding-box provenance;
- article and textbook structure behavior;
- warnings for ambiguous or image-only pages;
- cache invalidation by source and processor version;
- lazy loading of optional dependencies;
- streaming behavior for large inputs;
- absence of destination-specific assumptions;
- no source-file mutation.

Private corpora may be used for local acceptance testing, but their paths,
metadata, and content are not product fixtures.

## Architectural Invariants

1. Source documents are never modified.
2. Extracted objects are destination-independent.
3. Every derived object retains transitive source provenance.
4. Raw extraction survives semantic cleanup.
5. Expensive processing can be deferred and cached.
6. User naming and layout conventions are injected policies.
7. Search and destination storage remain consumer concerns.
8. Optional adapters do not burden base-package imports.
