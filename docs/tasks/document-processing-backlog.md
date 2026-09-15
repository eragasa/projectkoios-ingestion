# Document-processing backlog

## Status and rules

All tasks are proposed and independently reviewable. They preserve the accepted
output-independent PDF-ingestion architecture. Optional OCR or model libraries
must remain lazy adapters. Raw extraction is immutable evidence; derived output
is append-only.

## Foundation tasks

### ING-CACHE-01 — Filesystem extraction cache

Implement the existing `ExtractionCache` protocol using content-addressed,
versioned files beneath an injected cache root.

**Depends on:** current extraction contracts.

**Deliverables:** atomic `get` and `put`, cache manifest, corruption detection,
and CLI cache reuse.

**Acceptance:** unchanged source bytes and configuration avoid re-extraction;
extractor-version or source-hash changes miss the cache; interrupted writes do
not create valid entries; cache paths never escape the supplied root.

### ING-REGION-01 — Bounded PDF region renderer

Define `PageRegionSelection` and `RenderedRegion`, then implement a lazy
PyMuPDF renderer for selected pages or bounding boxes.

**Depends on:** current `SourceSpan` and exact source-blob identity.

**Deliverables:** destination-independent PNG bytes or asset descriptors,
resolution and color configuration, source bounding box, content hash, and
processor identity.

**Acceptance:** only selected regions are rendered; coordinates round-trip;
stable inputs give stable hashes; full-corpus rendering is not the default.

### ING-LAYOUT-01 — Reading-order and column analysis

Replace the current heuristic warning with a processor that proposes ordered
text blocks and column groups without changing raw block order.

**Depends on:** `ING-CACHE-01`.

**Deliverables:** layout hypotheses, evidence, confidence, and ambiguity
warnings.

**Acceptance:** fixtures cover one-column, two-column, spanning headings,
footnotes, and sidebars; uncertain cases remain uncertain; raw blocks are still
available.

### ING-QUALITY-01 — Redistributable PDF fixture matrix

Build generated or openly licensed fixtures for born-digital text, two-column
layout, equations, tables, figures, page labels, blank pages, and image-only
pages.

**Depends on:** none.

**Deliverables:** fixture provenance, generation scripts where possible, and
expected extraction assertions.

**Acceptance:** no private corpus enters Git; fixture rights are documented;
source files and expected outputs have checksums.

## OCR tasks

### ING-OCR-01 — OCR request and result contracts

Define bounded OCR selections, page-image inputs, token or line outputs,
coordinates, language configuration, confidence, warnings, and cache identity.

**Depends on:** `ING-REGION-01`.

**Acceptance:** the contracts represent partial failure and mixed native/OCR
pages without selecting an OCR engine or Markdown format.

### ING-OCR-02 — Tesseract OCR adapter

Implement a lazy, subprocess-isolated Tesseract adapter for explicitly selected
regions.

**Depends on:** `ING-OCR-01`, `ING-CACHE-01`.

**Acceptance:** missing executable produces a typed failure; language and engine
versions enter the cache key; native text is not silently replaced; tests use a
small redistributable image fixture.

### ING-OCR-03 — Native-text/OCR reconciliation

Propose a merged reading stream while retaining both native and OCR evidence.

**Depends on:** `ING-OCR-02`, `ING-LAYOUT-01`.

**Acceptance:** duplicate lines are identified, disagreements become warnings,
and a consumer can select either original stream.

## Structural tasks

### ING-STRUCTURE-01 — Article structure analyzer

Detect title, author block, abstract, keywords, sections, bibliography, and
appendices using bookmarks, numbered headings, font evidence, and bounded
fallbacks.

**Depends on:** `ING-LAYOUT-01`, `ING-QUALITY-01`.

**Acceptance:** every node points to source spans; heading level and reading
order have confidence; reciprocal hierarchy invariants pass; bibliography
entries are observations, not approved reference records.

### ING-EQUATION-01 — Equation candidate detection

Detect display and inline equation regions using PDF object, font, geometry,
and surrounding-text evidence.

**Depends on:** `ING-LAYOUT-01`, `ING-REGION-01`.

**Acceptance:** candidates retain rendered regions and surrounding locators;
numbered equations preserve source labels; the task makes no claim that symbols
have been interpreted correctly.

### ING-EQUATION-02 — Equation transcription processor

Define and implement an adapter boundary for proposing MathML or LaTeX from a
selected equation region.

**Depends on:** `ING-EQUATION-01`, `ING-CACHE-01`.

**Acceptance:** processor and configuration versions enter provenance; source
image remains available; low-confidence symbols are marked; no proposal is
called proofread or accepted.

### ING-TABLE-01 — Table candidate detection

Detect table regions and associate titles, captions, notes, and source spans.

**Depends on:** `ING-LAYOUT-01`, `ING-REGION-01`.

**Acceptance:** fixtures cover ruled, unruled, multi-page, and merged-cell
tables; false or ambiguous candidates carry warnings.

### ING-TABLE-02 — Table structure reconstruction

Propose rows, columns, spans, headers, and cell text as a destination-independent
table model.

**Depends on:** `ING-TABLE-01`.

**Acceptance:** every cell resolves to source blocks or a rendered region;
merged cells and multi-page continuation are representable; Markdown rendering
is outside this task.

### ING-FIGURE-01 — Figure and caption extraction

Detect figures, subfigures, legends, and captions and produce selected-region or
embedded-image artifacts.

**Depends on:** `ING-REGION-01`, `ING-LAYOUT-01`.

**Acceptance:** figure/caption associations include confidence; crops are within
page bounds; hashes and exact source regions are recorded; diagrams made from
PDF drawing commands are supported through rendering.

### ING-FIGURE-02 — Figure relevance proposal protocol

Define a processor that may propose which figures are necessary for a review
question without deleting or suppressing other detected figures.

**Depends on:** `ING-FIGURE-01`.

**Acceptance:** relevance is a scored proposal with stated rationale and review
question; selection is not represented as source fact or scientific acceptance.

## Composition tasks

### ING-JIT-01 — Bounded processing coordinator

Implement `ProcessingSelection`, processor invocation, derived cache keys,
partial completion, and retry behavior.

**Depends on:** `ING-CACHE-01` and at least one bounded processor.

**Acceptance:** a page, region, or structure-node selection can be processed
without invoking work on unselected pages; partial failures remain inspectable.

### ING-TRANSCRIPT-01 — Structured transcription proposal

Compose ordered prose, headings, equation candidates, tables, figures, and page
anchors into a destination-independent transcription model.

**Depends on:** `ING-STRUCTURE-01`, `ING-EQUATION-01`, `ING-TABLE-02`, and
`ING-FIGURE-01`.

**Acceptance:** normalized text links to raw blocks; omissions and uncertain
ordering are explicit; the result contains no citekey, vault path, Obsidian
syntax, reading status, or scientific-acceptance status.

### ING-PROVENANCE-01 — Derivation audit validator

Validate transitive provenance across raw blocks, OCR, layout, structure,
equations, tables, figures, and transcription composition.

**Depends on:** `ING-JIT-01`, `ING-TRANSCRIPT-01`.

**Acceptance:** orphan derived objects, wrong source blobs, out-of-range regions,
and missing processor versions fail validation.
