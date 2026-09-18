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

## Document Processing Model

The implemented cold PDF adapter uses PyMuPDF behind a lazy optional dependency
boundary. It records text blocks in PyMuPDF's native block order, image
references with media and mask identities, bounding boxes, physical pages,
printed labels, bookmarks, source hashes, page rotation, and low-text warnings.
Coordinates and matching dimensions use points relative to the unrotated crop box's
top-left corner. Cold extraction never applies PyMuPDF's optional reading-order
sort. The separate `DeterministicLayoutProcessor` proposes page-local ordered
text references and geometry-backed groups while preserving the complete raw
block sequence. It keeps sidebars, overlaps, weak separation, and unsupported
spanning arrangements explicitly uncertain. The implemented bounded region
adapter renders only explicit full-page or bounding-box selections to in-memory
PNG evidence. Implemented OCR contracts bind explicit ordered selections to
that exact evidence and define bounded token/line, status, warning, coordinate,
and cache identities behind an injected protocol. The implemented
`TesseractOCRProcessor` is a lazy, no-shell, per-selection POSIX subprocess
adapter with exact traineddata identities. The separate
`DeterministicOCRReconciler` consumes one exact OCR selection plus its verified
native page/layout evidence and proposes duplicate, disagreement, native-only,
and OCR-only relationships without replacing either evidence stream. The
`DeterministicArticleStructureAnalyzer` now proposes source-backed article front
matter, headings, hierarchy, bibliography observations, and appendices from
exact page-layout evidence. The bounded `DeterministicEquationCandidateDetector`
proposes display and inline equation-shaped regions while retaining exact text,
context, labels, and rendered source evidence. A compact equation-retrieval projection retains native equation text, immediate context, locators, geometry, image identities, and uncertainty without carrying PNG bytes into a search index. A separate enrichment stage conservatively assembles geometric fragments, retains exact and sanitized layers, invokes an explicitly identified image-to-LaTeX adapter, derives MathML, and partitions records into primary, auxiliary, and rejected retrieval tiers without accepting the mathematics. Engine-neutral equation-
transcription contracts then allow injected adapters to propose LaTeX or MathML
without turning recognition output into accepted source fact. Bounded table-
candidate detection combines exact layout, PDF vector-rule observations, and
rendered regions. The separate `DeterministicTableStructureReconstructor`
proposes a complete destination-neutral cell grid, spans, headers, and explicit
page continuations while preserving exact source and rendered evidence. Bounded
figure detection separately retains exact embedded image/mask artifacts and
renders captioned PDF drawing-command diagrams with source-backed caption,
subfigure-label, and legend associations. Engine-neutral relevance contracts
then allow an injected processor to score those exact candidates against one
review question without deleting proposed-not-necessary figures. A bounded JIT
coordinator resolves page, region, and structure-node selections into isolated
work items, invokes one injected processor per selection, preserves retries and
partial failures, and computes separate derived cache identities. Deterministic
structured composition then proposes ordered page anchors, prose, headings, equations, tables, and figures while retaining every exact upstream object and making omissions and uncertain order explicit. A separate deterministic clean-transcript projection removes only typed repeated margins, page numbers, control-only blocks, soft hyphens, conservative line-break hyphenation, and whitespace artifacts while retaining exact raw block evidence, exclusions, uncertainty, and proposed layout order.

PDF document support follows an output-independent pipeline:

```text
SourceDocument
    -> SourceExtractor
    -> ExtractedDocument
    -> optional PageLayoutProcessor
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
- page text blocks in extractor-native order and source coordinates;
- source-object references and image bounding boxes;
- extraction quality and warnings.

Font metrics, drawing commands, proposed reading order, and equation, figure,
example, or problem candidates require separate derived contracts rather than
being implied by the current cold extraction record.

Cold results are reusable by every downstream destination. The implemented
filesystem cache reuses unchanged sources when the contract/cache format,
logical and exact blob identities, extractor and installed-backend versions,
and extraction-affecting configuration match. It stores canonical JSON
contracts in hash-sharded version directories beneath an injected root.

### Just-in-time processing

An application may request enrichment of a selected page range or structural
unit. JIT work can include OCR, page-region rendering, expensive structural
analysis, or semantic cleanup through injected processors. Deterministic
article structure can also be derived for an extracted document through the
injected `ArticleStructureAnalyzer` boundary. The implemented
`PageRegionRenderer` boundary accepts only an explicit, non-empty ordered set
of page or bounding-box selections; it has no automatic whole-document path.
Its PyMuPDF adapter returns PNG bytes without publishing files and checks
configured selection, per-region pixel-dimension, pixel-count, raster-byte,
and aggregate request limits before the first rendering allocation. Fractional
clips round outward to device pixels; results retain the requested box,
effective source footprint, page rotation, and pixel-to-source transform.
Bounded OCR requests retain those complete `RenderedRegion` values rather than
caller-recreated image metadata. OCR results preserve selection order and keep
source/page-verified native text references as coexistence evidence while
token/line streams remain separate. Completed, partial, and failed outcomes
carry explicit output, warning, and typed-failure invariants; completed empty
output represents a successfully processed blank region. The contract layer
selects no engine. Applications may explicitly inject `TesseractOCRProcessor`,
which stages exact PNG and traineddata snapshots in a private temporary
directory, invokes one bounded subprocess per selection, strictly interprets
TSV, and cleans up without durable publication. Missing execution resources,
timeouts, capture overflow, malformed output, and nonzero exits remain explicit
selection-local outcomes rather than silent native-text replacement.

An application may separately inject `OCRReconciler`. The implemented
deterministic reconciler requires line output and exact page/layout provenance,
uses bounded normalized-text and source-geometry matching, rejects conflicting
known geometry, and leaves near-tied candidates unmatched. Its result retains
exact native blocks, exact OCR lines, explicit one-to-one matches, warnings,
and a complete proposed merged sequence. Duplicate proposals preserve native
text; disagreement proposals contain no chosen text. Native-only entries retain
native text and unmatched OCR lines follow in OCR order. The proposal is not
semantic correction, proofread transcription, scientific validation, or human
acceptance, and it is not written to the raw extraction cache.

Equation-candidate detection is another explicit derived stage. It consumes
exact extraction/layout evidence, scans bounded native text, and asks an injected
region renderer only for candidate boxes. Inline offsets remain tied to native
text while their crop is explicitly block-scoped. Weak candidates and missing
geometry remain warnings; no detected characters are interpreted as correct
mathematics.

An application may pass selected candidates to an
`EquationTranscriptionProcessor`. The request retains each exact candidate and
PNG; the adapter returns ordered LaTeX and/or MathML proposals with explicit
processor/backend/model identity, substring confidence coverage, warnings, and
typed failure evidence. Low-confidence and unassessed substrings are marked and
warning-linked. The boundary executes no default engine and publishes no file.

Table-candidate detection is another explicit derived stage. Its default lazy
rule inspector retains bounded axis-aligned PDF drawing segments and ignored
item counts; the detector combines those observations with native text
alignment and nearby lexical associations. It renders only proposed regions.
Explicit continuation labels may join adjacent pages, while merged-cell signals
and prose-like geometry remain warned observations.

An application may then inject `TableStructureReconstructor`. The deterministic
implementation consumes the complete exact detection result. Complete vector
grids or native-text midpoint geometry propose columns and page-local rows;
every grid position becomes a cell grounded in exact source blocks/spans or the
retained candidate-region PNG. Explicit header text can propose roles. Merged
signals remain ambiguous spans, and multi-page continuations retain separate
rows and repeated headers rather than silently merging cells. Warnings preserve
unruled or mixed boundary geometry, unresolved headers, empty or multi-block
cells, low confidence, and inherited candidate ambiguity. This stage changes
no source text, renders no Markdown, and claims no table correctness.

Figure-candidate detection is another explicit derived stage. The default lazy
inspector re-verifies embedded image and mask bytes against raw content-addressed
references and retains bounded PDF drawing-object extents. Embedded images are
components directly. Positive-area groups assembled from drawing commands,
including zero-area line extents, are promoted only with a nearby explicit
figure caption and rendered through the region boundary. Multiple visuals that
share one caption remain ordered subfigure components. Explicit caption,
subfigure-label, and legend blocks retain unchanged text, spans, method evidence,
and confidence. Captionless embedded images stay ambiguous; unassociated drawing
groups are not silently promoted. No pixel semantics or scientific relevance is
inferred.

An application may separately inject `FigureRelevanceProcessor`. A request
retains complete exact detection results and one candidate ID per ordered
selection, plus the unchanged review question. A processor returns a normalized,
method-described relevance score, optional confidence, rationale, and exact
component/association evidence references. Explicit proposal levels distinguish
necessary, supporting, and not-necessary recommendations without representing
any as source fact or acceptance. Ordered completed, partial, and failed
outcomes preserve every input selection, warnings, and typed failures. The
boundary runs no default model and suppresses no candidate.

For generic JIT composition, `BoundedProcessingCoordinator` resolves each exact
`ProcessingSelection` to a `ProcessingWorkItem` containing only selected full
pages, source spans, structure nodes, and input object IDs. It does not pass the
complete document or source bytes to `ProcessingProcessor`. The processor
returns bounded immutable artifacts plus warnings and typed failures. Fully
failed, wholly retryable invocations may be retried within the configured
attempt bound; partial output is retained without automatic retry or merge.
Every attempt remains inspectable, and non-retryable selection failure does not
prevent later selections from running.

An optional `DerivedProcessingCache` may reuse exact completed or partial
selection results. Failed results are never written. Cache keys bind the exact
resolved selection, all coordination limits, processor/backend/configuration
identity, and ordered immutable resources. The coordinator supplies no cache
implementation and does not mix derived results into raw `ExtractionCache`.

The ingestion package defines and coordinates the request and result contracts.
It does not choose when retrieval should trigger the request, which model to
run, or where a projected artifact should be written.

JIT cache identity includes exact logical/blob/image and ordered selection
evidence, contract version, processor/backend versions, and the complete
processor configuration. The OCR boundary additionally includes native-text
coexistence references, ordered canonical semantic language tags, output mode,
every resource limit, and the exact backend language-resource names and
immutable identities selected for those tags. The Tesseract adapter also folds
its timeout, capture/resource limits, page segmentation mode, and engine mode
into its effective processor version, while the normalized backend report and
executable bytes have separate hashes in backend identity. A processor,
backend, adapter setting, language mapping, or resource change invalidates its
derived result without invalidating raw extraction. Equation-transcription
cache identity likewise includes its contract/configuration versions, exact
candidate image, requested formats and limits, processor/backend versions, and
model/resource identities. Derived OCR, reconciliation, and equation-
transcription storage remain deferred and are not added to the raw
`ExtractionCache`. Table-candidate identity likewise includes exact document,
layout, vector-rule, renderer, detector, and configuration evidence; table
candidates are also excluded from the raw cache. Table-structure identity binds
the exact detection result, complete reconstruction configuration, processor
version, proposed topology and text evidence, rendered-region identities, and
warning links. Table structures likewise remain derived outputs outside the raw
cache. Figure identity includes the exact document/layout/embedded/drawing
inspection evidence, complete configuration and processor versions, exact
embedded hashes, rendered-region identities, associations, topology, and
warnings. Figure candidates also remain outside the raw cache. Figure-relevance
cache identity additionally includes the exact review question, ordered complete
detection evidence, configured thresholds and bounds, processor/backend
versions, and immutable model/prompt/resource identities. Relevance results are
not added to the raw extraction cache. Generic JIT cache identity separately
binds the resolved selected evidence, coordinator contract and configuration,
and processor/backend/configuration/resource provenance. Only exact completed or
partial selection results are eligible for an injected derived cache.
Structured-transcription cache identity binds the exact document and complete
structure/equation/table/figure result identities, the whitespace-normalization
method, all composition limits, and composer version. Structured transcription also remains outside the raw extraction cache. Clean-transcript identity binds the exact structured-transcription result, layouts, included raw blocks and cleaned text, typed exclusions, transformation counts, page projections, processor/configuration identity, and final UTF-8 hash. The batch materializer persists only the compact clean projection, plain text, complete audit report, and an identity manifest; bulky deterministic intermediate graphs remain reconstructible rather than duplicated on disk.

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

Structure detection uses available evidence in descending order of reliability:

1. extracted metadata corroborated by exact source text and PDF bookmarks or
   table-of-contents destinations;
2. numbered and explicit article-heading patterns;
3. deterministic page-layout order and source geometry;
4. bounded, explicitly warned fallback.

The implemented article analyzer requires one exact layout result per page,
retains exact source spans and block IDs, records separate heading and reading
order confidence, and emits a reciprocal acyclic hierarchy. It groups explicit
front matter, recognizes conservative article section names, and records
bibliography entries only as observations. The current raw extraction contract
does not retain font metrics, so font hierarchy is neither inferred nor
invented. Every inferred node records its evidence, confidence, and warnings.
Consumers can inspect or override uncertain structure without re-reading the
source PDF.

## Equation Candidate Model

Equation candidates are append-only derived observations. Display candidates
retain exact block text and source spans; inline candidates retain exact
source-relative offsets. Both retain immediate same-page block locators and one
validated rendered region. The rendered source selection may be padded but must
contain all candidate geometry. A numbered source label remains an uninterpreted
string.

The deterministic detector uses explicit delimiters and transparent native-text
signals together with layout order and source geometry. Confidence selects only
`proposed` or `ambiguous`; it cannot express accepted, proofread, scientifically
validated, or human-approved. The raw extraction contract does not currently
retain font metrics or drawing-command objects, so the detector neither invents
nor claims those evidence sources.

## Equation Transcription Model

A transcription selection embeds one complete equation candidate rather than a
caller-recreated image reference. Configuration requests ordered LaTeX and/or
MathML formats and bounds images, outputs, confidence substrings, warnings,
resources, and aggregate retained evidence. A completed selection requires all
requested formats and confidence-assessed coverage of every non-whitespace
output character. Partial and failed selections retain typed failure and warning
evidence.

Processor and backend versions plus immutable model/vocabulary identities enter
the derived cache key with the exact candidate image and complete configuration.
The output remains a proposal: status and confidence never mean proofread,
mathematically correct, scientifically validated, accepted, or human-approved.
No transcription result enters the cold extraction cache.

## Table Candidate Model

A table candidate contains one or more page-ordered regions. Each region retains
exact source blocks/spans, row and column band counts, contributing PDF rule
segments, possible merged-cell block signals, and one validated rendered PNG.
Candidate-level associations retain unchanged title, caption, note, and explicit
continuation text as separate source evidence.

The deterministic detector proposes `ruled`, `unruled`, or `mixed` boundaries
and only `proposed` or `ambiguous` status. Explicit continuation labels plus
compatible normalized columns may join adjacent pages. A merged-row signal is
not a reconstructed span, and completed detection is not semantic correctness,
scientific validation, publication suitability, or human acceptance. Derived
table candidates are not stored in the cold extraction cache.

## Structured Transcription Model

The deterministic composer consumes one exact document and complete exact
structure analysis, equation detection, table reconstruction, and figure
detection results. It produces destination-neutral page anchors, normalized
heading/prose items, and typed equation/table/figure references. It does not
flatten tables or figures into prose and does not replace equation candidates
with recognized mathematics.

Text normalization only joins exact ordered source strings, collapses Unicode
whitespace runs to one ASCII space, and trims the result. Exact raw strings,
block IDs, and spans remain adjacent evidence. Typed items retain complete
upstream objects through the input contract. Every raw block is accounted for by
an item or an explicit omission; duplicate typed/structural representation and
unrepresented non-text blocks cannot disappear silently.

Ordering records whether it uses page anchoring, proposed source geometry,
proposed structure reading order, or a warned uncertain source-order fallback.
Stable item identity is source-local and excludes global list position, while
the result identity includes the complete order. `proposed` and
`proposed_with_uncertainty` are composition states only, not proofread,
scientifically validated, accepted, or publication-ready states. The model owns
no Markdown, citekeys, filenames, vault paths, Obsidian syntax, reading status,
or scientific-acceptance field.

## Clean Transcript Projection Model

The deterministic projector consumes one complete structured-transcription result and its exact page layouts. Each included record retains the root block ID, exact raw text, exact source spans, physical and printed page, proposed order, cleaned text, and deterministic transformation counts. Each excluded record retains the same root evidence and a typed `repeated_margin`, `page_number`, or `empty_after_sanitization` reason. Repeated margins require matching normalized margin evidence across a bounded minimum number and fraction of pages; standalone decimal or lowercase Roman page labels are excluded only in page margins.

Cleanup does not use a language model or dictionary. It removes soft hyphens, replaces bounded C0 control characters, joins only ASCII letter sequences split by a hyphen plus line break when the continuation begins lowercase, collapses Unicode whitespace, and emits explicit page markers. It does not normalize Unicode compatibility characters, repair equations, reorder words within a block, infer missing text, or claim semantic correction. Proposed multi-column order and any raw-order fallback remain warned evidence.

The projection is `automated_unreviewed` regardless of apparent quality. It is a source-linked retrieval input, not a proofread edition, canonical bibliography decision, scientific validation, manuscript support decision, or Markdown note. Generated relevance prose must never be indexed back into the extraction-derived corpus.

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

The derivation-audit boundary accepts exact source bytes and explicitly registered typed artifacts. It validates only supplied layers, but a supplied downstream layer cannot hide an unregistered dependency: embedded OCR, layout, detection, structure, transcription, or clean-projection inputs must match the registered upstream object exactly. Clean records and exclusions must reproduce exact root block text/spans, remain on their root page, preserve page-local record order, and consolidate to the artifact text exactly. The validator traverses immutable in-memory contracts rather than Markdown, vault paths, or storage records. It produces stable findings and a stable report without repairing, normalizing, publishing, or accepting evidence.

A derivation audit is a fail-closed software-integrity gate, not a semantic validator. Passing it confirms that source identities, regions, processor identities, hashes, stable IDs, and references form one internally consistent bounded graph. Scientific, mathematical, pedagogical, publication, and lifecycle judgments remain outside ingestion.

## Artifact Ownership

Machine-generated extraction artifacts are reproducible and replaceable.
Human-authored artifacts are outside this repository and must never be treated
as regeneration targets.

The ingestion package may return bytes, objects, iterators, manifests, or
artifact descriptions. Writing them to a filesystem or vault requires an
explicit consumer-provided writer.

## Extension Protocols

The architecture depends on small protocols:

- `SourceExtractor` converts a source into normalized extraction objects;
- `StructuralAnalyzer` proposes a source-backed document hierarchy;
- `ArticleStructureAnalyzer` specializes that boundary for articles;
- `DocumentProcessor` derives enriched content while preserving provenance;
- `ChunkProducer` converts structured content into source-backed chunks;
- `ExtractionCache` retrieves and stores versioned extraction results;
- `ProcessingProcessor` derives artifacts from one exact bounded work item;
- `DerivedProcessingCache` optionally stores non-failed derived selection
  results;
- `OCRProcessor` accepts bounded OCR requests and returns ordered results;
- `OCRReconciler` proposes bounded native/OCR evidence relationships;
- `EquationCandidateDetector` proposes bounded rendered equation evidence;
- `EquationTranscriptionProcessor` proposes bounded LaTeX/MathML evidence;
- `TableCandidateDetector` proposes bounded rendered table evidence;
- `StructuredTranscriptionComposer` composes exact typed evidence without
  choosing a destination;
- `ArtifactWriter` accepts destination-neutral artifacts;
- `ChunkIndexWriter` accepts chunk streams.

Concrete implementations depend inward on these contracts. Optional PDF,
OCR, or model dependencies must not be imported merely by importing the base
package. The generic coordinator catches selection-local processor failures but
requires truthful processor identity resolution; it supplies no engine, source-
byte loader, filesystem cache, or execution sandbox.

## Dependency Rules

1. Domain models do not import PDF, search, model-provider, or vault libraries.
2. PDF libraries are confined to PDF adapters.
3. Search implementations depend on ingestion contracts, not the reverse.
4. Destination renderers depend on ingestion results, not the reverse.
5. External boundary models may validate serialized input, while internal
   models prefer dataclasses or ordinary classes.
6. Optional dependencies are loaded only when their adapter is used.

## Trust and Resource Boundary

Cold extraction parses the complete PDF in the caller's process and currently
reads the complete source blob into memory. PyMuPDF includes complex native
parsing code; successful parsing is not validation that a PDF is trustworthy.
Callers accepting untrusted documents are responsible for source-size, page
count, time, memory, and concurrency limits before invoking cold extraction or
region rendering. Deployments whose threat model requires containment should
invoke the CLI or library inside an operating-system sandbox, container, or
similarly restricted worker. This milestone does not provide a sandbox,
daemon, or source-admission service. One shared ingestion source-admission
policy must be established before applications accept untrusted or unbounded
documents; a renderer-only byte limit would not satisfy that boundary.

## Failure and Confidence Model

Extraction does not silently discard uncertainty. A result may contain usable
content and warnings at the same time. The cold extractor emits low-text or
likely-scan warnings; layout ambiguity belongs to the separate layout result.
The layout processor emits source-backed warnings for overlapping blocks,
touching, weak, sparse, or staggered column evidence, sidebars, uncertain bottom
text, nonzero page rotation, unsupported spanning positions, and documented
geometry or payload exclusions. Unsupported coordinate systems fail closed. It
treats an absent printed page label as normal optional
evidence rather than a warning. Malformed and encrypted inputs are fatal errors
and do not produce a result. The Tesseract OCR adapter adds typed, source-linked
warning/failure evidence for unavailable execution resources, resource limits,
backend errors, and invalid TSV. Reconciliation adds object-linked warnings for
incomplete OCR, inherited layout uncertainty, skipped comparisons, ambiguous
matches, text disagreements, and conservatively appended OCR-only order.
Equation detection adds warnings for weak candidates, missing geometry, and
ambiguous inline offset mapping. Equation transcription adds selection-local
warnings for low or unavailable confidence and typed rejected-input, resource,
availability, backend, format, invalid-output, and incomplete-output failures.
Table detection warns ambiguous or prose-like candidates, possible merged-cell
rows, and mixed rule evidence. Deferred figure processors may add their own
source-backed warnings when implemented.

Fatal errors prevent creation of a valid result. Recoverable uncertainty is
represented in the result manifest. OCR selection failures are typed and linked
to warning evidence; mixed outcomes produce an explicit partial result without
allowing failed selections to claim output. A completed empty OCR result is a
successful observation of no recognized text. Adapter confidence is optional
and records its method, method version, and scale rather than implying a
probability or proofread-transcription claim. Semantic language tags remain
separate from the exact backend language-resource identities used in future
cache keys. Region rendering rejects source metadata
mismatches, encrypted or malformed PDFs, invalid pages or coordinates, and
resource-limit violations. It does not normalize or clip requested source
boxes.

## Idempotency

Given the same source bytes, adapter version, PyMuPDF backend version, and
configuration, deterministic extraction must produce equivalent normalized
content and stable identifiers. The concrete backend version participates in
the manifest extractor identity and extraction cache key. Region rendering
similarly records adapter, backend, selection, and complete configuration
identity alongside the exact PNG hash. Locator and printed-label display data
do not enter stable region identity. Stable renderer bytes are demonstrated
for repeated execution with one concrete installed PyMuPDF build; equivalence
across distinct native builds reporting the same version is not claimed.

Cache writes and downstream delivery must be retryable. Filesystem cache
entries are flushed to exclusive same-directory temporaries and atomically
published without clobbering an existing path. An existing exact-key entry must
validate before it is accepted; unrelated or corrupt files are preserved and
reported. Readers validate envelope, payload, stable-object, and cross-source
identities. Concurrent same-key writers accept the first valid entry and cannot
publish a partial entry. Cache corruption is an explicit error rather than a
miss. Uncatchable termination can leave ignored temporary files, and durability
of the latest publication remains subject to the filesystem honoring directory
sync. This backend fails closed before root access unless required POSIX
capabilities for descriptor-relative and no-follow operations are present;
uncached extraction remains available. This repository does not assume that a
consumer supports destructive replacement. CLI publication
preflights every requested path, creates files exclusively, and removes files
and directories created by the current invocation after a handled publication
failure. There is no portable atomic transaction spanning multiple output
paths, so process termination or machine failure can leave partial artifacts;
no-overwrite behavior then requires explicit inspection and cleanup.

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
- fail-closed transitive derivation audits and stable findings;
- article and textbook structure behavior;
- layout warnings for ambiguous pages and extraction warnings for image-only pages;
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
