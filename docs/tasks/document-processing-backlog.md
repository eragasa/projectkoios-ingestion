# Document-processing backlog

## Status and rules

Tasks are proposed and independently reviewable unless explicitly marked
implemented. They preserve the accepted output-independent PDF-ingestion
architecture. Optional OCR or model libraries must remain lazy adapters. Raw
extraction is immutable evidence; derived output is append-only.

## Foundation tasks

### ING-CACHE-01 — Filesystem extraction cache (implemented)

`FilesystemExtractionCache` implements the existing `ExtractionCache` protocol
with canonical JSON envelopes below an injected root. Its deterministic key
includes cache format and extraction contract versions, logical and exact blob
source identity, extractor/installed-backend identity, and the normalized
configuration digest. The versioned, hash-sharded path is derived from a SHA-256
digest of the complete key rather than caller-controlled path text.

Every read verifies the path/key hash, payload hash, envelope evidence, complete
reconstructed `ExtractionResult`, stable object identities, and cross-field
source/span identities. Malformed or truncated JSON, invalid Unicode, duplicate
fields, unsupported versions, identity mismatches, and invalid contracts raise
explicit cache errors rather than becoming misses. Managed directories and
entries are opened without following symlinks.

Writes flush a same-directory exclusive temporary file and atomically publish it
only if the entry path is absent. An existing valid exact-key entry is accepted;
an unrelated or corrupt regular file is preserved and reported. The containing
directory is synced and handled failures remove their temporary. Concurrent
identical writers are safe: a reader observes the first complete validated
result. A machine or filesystem failure can still lose the most recent
publication where durable directory sync is not honored; abandoned temporaries
from uncatchable process termination are ignored by readers.

The backend checks for required POSIX descriptor-relative, directory/no-follow,
and no-follow hard-link capabilities before accessing its root and fails closed
with `ExtractionCacheSafetyError` if they are unavailable. Uncached extraction
remains usable on unsupported platforms; a weaker portable cache fallback is
not implemented.

The PDF CLI's optional `--cache-root` reuses a hit without extraction and fills a
miss before artifact publication. Existing artifact no-overwrite behavior is
unchanged. Cache retention, eviction, migration of future formats, distributed
coordination, and repair of corrupt entries are deferred/non-goals.

**Depends on:** current extraction contracts.

**Validation:** cache unit and CLI hit tests, the PDF fixture matrix, full test
and static-analysis suites.

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

### ING-QUALITY-01 — Redistributable PDF fixture matrix (implemented)

The compact synthetic matrix in `tests/fixtures/pdf/` covers born-digital text,
two-column layout, equations, tables, figures, printed page labels, blank
pages, and image-only pages. Its machine-readable manifest records per-case
purpose, provenance, MIT rights, exact source and expected-output SHA-256
identities, sizes, and focused cold-extraction assertions. The checked-in
sources are canonical because generation is PyMuPDF-version-sensitive;
`scripts/pdf_fixture_matrix.py` provides explicit refresh and verification
modes.

The maintained assertions are limited to raw text/image blocks, native order,
geometry, labels, asset identity/media type, the extractor's text-density
quality metric, and explicit cold-extraction warnings. OCR, equation
understanding, table reconstruction, figure semantics,
layout analysis, scientific validation, and proofread transcription remain
deferred to their respective tasks or downstream review.

**Depends on:** none.

**Validation:** `.venv/bin/python scripts/pdf_fixture_matrix.py --verify`.

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
