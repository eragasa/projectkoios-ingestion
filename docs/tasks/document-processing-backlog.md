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

### ING-REGION-01 — Bounded PDF region renderer (implemented)

Immutable `PageRegionSelection`, `RegionRenderConfiguration`, and
`RenderedRegion` contracts are exported with the `PageRegionRenderer` protocol.
`PyMuPdfRegionRenderer` lazily loads PyMuPDF and returns in-memory,
destination-independent PNG bytes for a required non-empty ordered selection.
A selection explicitly chooses either a full physical page or one strict
positive-area bounding box in the declared unrotated crop-box point coordinate
system. Invalid pages and non-finite, inverted, empty, negative, or out-of-page
boxes fail rather than being normalized or clipped.

The renderer validates exact source bytes before parsing, preserves requested
order, coalesces identical selections within one request, maps source boxes
through page rotation, and records the physical page, exact printed label,
requested and effective source boxes, pixel-to-source transform and rounding,
logical and blob identities, resolution, opaque RGB/grayscale behavior, PNG
media type/size/dimensions/SHA-256, configuration digest, and adapter/backend
identities. Locator and printed-label display data do not enter the stable
region identity, whose complete evidence is validated on construction.

Defaults are 144 DPI, opaque RGB on white, at most 256 requested selections,
16,384 pixels on either output dimension, 25,000,000 output pixels, and
100,000,000 uncompressed raster bytes per region and across all unique regions
in one request. Iterable consumption stops at the selection limit plus one;
per-region and aggregate limits are calculated before the first pixmap
allocation. Source-size admission remains the caller's repository-wide PDF
trust-boundary responsibility. There is no empty or implicit render-all
operation and no filesystem publication. OCR, region detection,
layout/semantic interpretation, storage, and model calls are non-goals.

**Depends on:** current `SourceSpan` and exact source-blob identity.

**Validation:** focused synthetic crop-box/rotation/page-label tests, lazy
optional dependency tests, fixture verification, and full test/static-analysis
suites.

### ING-LAYOUT-01 — Reading-order and column analysis (implemented)

`DeterministicLayoutProcessor` produces immutable, page-local text layout
proposals without changing `ExtractedPage.blocks`. Results retain exact source
and physical-page identity, the complete native raw-block ID sequence,
source-spanned text references, explicitly non-text block IDs, a proposed text
order, documented geometry exclusions, and column/group hypotheses. Stable
result identity includes the layout contract, source page, input evidence,
processor version, and complete configuration digest.

Processor version 2 uses actual block-level vertical concurrency and minimum
flow extent to distinguish one column and two balanced columns. A spanning
heading must be wide, above both columns, intersect both column extents, and
cross the gutter. Separated bottom text follows main flow only with the
explicitly ambiguous group kind `footnote_candidate`; identical geometry can
be a footer or final paragraph. Overlap, touching or weak separation, sparse/staggered groups,
bridging top blocks, unsupported spanning positions, sidebars, and nonzero page
rotation use low-confidence explicit warnings rather than confident insertion
guesses. Unsupported coordinate systems are rejected. Confidence is a bounded
heuristic score, not a probability, transcription score, or scientific
validation claim.

Per-page preflight bounds are 1,024 total raw blocks, 512 text blocks, 2,048
total source spans, 4,096 characters per identity field, and 1,000,000 aggregate
identity characters before provenance validation and pair analysis.

The processor does not inspect text semantics. Non-text blocks remain in the
raw page and are recorded but excluded from text-layout claims. Raw kind/span
references are factory-validated against the input page. Missing geometry or a
missing string text payload is an explicit exclusion; text with no analyzable
geometry is ambiguous with zero confidence rather than empty. Group confidence
and warning associations participate in stable identity. OCR, tables, figures,
equations, semantic sections,
document-wide flow, publication, and derived caching remain out of scope. The
processor supports at most two confident columns, uses extracted ink geometry,
and cannot distinguish column geometry from tables or semantic footnotes;
complex pages require inspection of the low-confidence proposal and raw page.

The cold extractor's former `pdf.reading_order_uncertain` heuristic was removed
and its adapter version changed from 1 to 2, invalidating matching raw cache
entries. The additive page-rotation evidence uses extraction contract 2.2 and
also changes raw cache identity. The synthetic matrix covers
one-column, two-column, spanning-heading, footnote, sidebar, and weakly
separated ambiguous pages.

**Depends on:** `ING-CACHE-01`.

**Validation:** focused layout/extractor/cache tests, fixture verification, and
full test/static-analysis suites.

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

### ING-OCR-01 — OCR request and result contracts (implemented)

Immutable, destination-independent OCR contracts retain each exact validated
`RenderedRegion` as the page-image input to an explicit ordered selection.
Requests configure ordered canonical semantic language tags, token, line, or
token-and-line output, and deterministic hard-ceiling limits for
selections/images, image pixels/bytes, language and identity strings, output
counts/text, warnings, and aggregate result size.
Pixel boxes are finite, positive-area, image-bounded rectangles; source boxes
are derived and revalidated through the region's affine map in unrotated
crop-box coordinates, including rotated rendered images.

Per-selection completed, partial, and failed statuses roll up to an overall
status without dropping request order. A completed empty result represents a
successfully processed blank image. Partial and failed outcomes require a typed
failure linked to explicit warning evidence; failed selections cannot contain
successful output. Ordered native text references are verified against the
same extracted source page and retained only as coexistence evidence; OCR
output remains a separate stream. Confidence is optional and carries the
adapter's method, method version, and scale; it is not a probability,
proofreading result, or reconciliation claim.

The deterministic OCR cache key includes contract version, ordered exact
source/image/selection evidence, native block references, language/output
choices, every behavior/resource limit, processor/backend name and version, and
ordered language-resource names plus immutable digests or explicit
version identities. It defines only the cache identity boundary; it does not
extend `ExtractionCache`. `OCRProcessor` is an injected protocol whose
`identity_for` method exposes that descriptor before execution. No engine, adapter,
executable, model, output format, destination, storage, or native/OCR
reconciliation policy is selected or invoked by this task.

**Depends on:** `ING-REGION-01`.

**Validation:** focused OCR contract and region tests, fixture verification,
and full test/static-analysis suites.

### ING-OCR-02 — Tesseract OCR adapter (implemented)

`TesseractOCRProcessor` is a lazy, no-shell POSIX subprocess adapter for
explicitly selected regions. Callers provide immutable mappings from canonical
semantic language tags to safe Tesseract resource names and traineddata paths;
there is no implicit backend-language conversion. Pre-execution identity
contains hashes of the bounded normalized `tesseract --version` report and
executable, ordered language/resource mapping, exact traineddata SHA-256 values,
and an effective processor version covering timeout, capture/resource limits,
page segmentation mode, and optional
engine mode.

Each selected PNG and the exact requested traineddata bytes are staged in a
private temporary directory. Every selection gets an isolated process session,
fixed locale/thread environment, bounded stdout/stderr draining, timeout with
process-group termination, strict UTF-8 TSV validation, and cleanup. Word rows
become ordered tokens; grouped word evidence becomes optional lines. Confidence
retains explicit Tesseract/aggregation semantics. Blank TSV succeeds; usable
output from a nonzero invocation is partial; unavailable executables/resources,
unmapped languages, output overflow, timeout, invalid output, and contract
limits become typed failures. Raw stderr and temporary paths are not retained.
Native text remains separate and derived OCR storage is still deferred.

**Depends on:** `ING-OCR-01`, `ING-CACHE-01`.

**Validation:** hermetic executable-double tests cover engine/resource/cache
identity, all output modes, selection order, blank success, partial output,
missing executable/resource/language mapping, timeout, malformed output, and
capture/aggregate limits. The maintained wholly synthetic PNG fixture is
regenerated and verified by `scripts/ocr_fixture.py`; an environment-configured
real-engine smoke test remains optional.

### ING-OCR-03 — Native-text/OCR reconciliation (implemented)

`DeterministicOCRReconciler` consumes one exact OCR selection and requires the
matching extracted page and layout result whenever native references exist.
It preserves exact selected native blocks and exact OCR lines as independently
selectable streams. Native block lines become bounded comparison segments with
block/line provenance; normalization is used only for matching and never
replaces source text.

Known source geometry gates matching. Exact normalized text becomes a likely
duplicate only when available geometry does not contradict it. Similar text
becomes a disagreement only with sufficient geometry overlap. Matching is
one-to-one and deterministic; competing near-ties remain separate and produce
an ambiguity warning. The proposed merged stream covers every native segment
and OCR line exactly once as duplicate, disagreement, native-only, or OCR-only.
Duplicate/native-only/OCR-only proposals preserve an original payload;
disagreement proposals deliberately choose no text.

Configuration identities include all matching thresholds and hard limits for
blocks, segments, OCR lines, pair count, comparison work, comparison/retained
text, warnings, and retained output. Completed blank, OCR-only, native-only,
partial/failed, rotated,
and ambiguous evidence is represented without silent replacement. The result
claims neither semantic correction, proofread accuracy, scientific validation,
human acceptance, nor publication suitability. Derived reconciliation storage
remains deferred.

**Depends on:** `ING-OCR-02`, `ING-LAYOUT-01`.

**Validation:** focused reconciliation tests cover duplicates, disagreements,
OCR-only, native-only, blank, rotated, ambiguous, stale-provenance, immutable
identity, and pre-matching resource bounds; full tests and static analysis pass.

## Structural tasks

### ING-STRUCTURE-01 — Article structure analyzer (implemented)

`DeterministicArticleStructureAnalyzer` consumes one exact layout result per
extracted page and proposes an immutable article hierarchy. It detects
metadata-correlated or explicitly warned fallback titles, explicit author
lines, abstracts and bounded abstract bodies, keyword lines, numbered and
conservative known-name sections/subsections, bibliographies, bibliography
entries, and appendices. Matching table-of-contents/bookmark evidence strengthens
one unique source heading but never creates unanchored text.

Structure contract version 1.0 adds exact source-block links, heading level and
confidence, contiguous reading order and confidence, transparent evidence
status, stable analysis identity, and bounded processor/layout provenance.
Parent/child links must be reciprocal and acyclic. Bibliography entries are
forced to `observed`; the enum deliberately contains no accepted or validated
state. Missing/fallback titles, layout uncertainty, empty bibliographies, and
missing text remain explicit warnings.

The current raw extraction contract does not retain font metrics. This analyzer
therefore uses table-of-contents evidence, numbering, explicit labels, known
headings, geometry, and layout order rather than inventing font observations.
Configuration hard-bounds pages, blocks/text, nodes, warnings, heading length,
abstract extent, and bibliography entries. It writes no files, stores no
derived result, and claims no semantic correction, scientific validation, or
human acceptance.

**Depends on:** `ING-LAYOUT-01`, `ING-QUALITY-01`.

**Validation:** focused tests cover full front matter/section/bibliography/
appendix hierarchy, exact table-of-contents corroboration, abstract grouping,
fallback and empty evidence, stale layout rejection, resource bounds, stable
immutable identity, reciprocal hierarchy, and bibliography observation status;
full fixture and static-analysis suites pass.

### ING-EQUATION-01 — Equation candidate detection (implemented)

`DeterministicEquationCandidateDetector` consumes an exact extracted document,
one exact layout result per page, and the matching PDF bytes only when a region
must be rendered. It proposes bounded display candidates from transparent
relation/operator/variable/strong-symbol/LaTeX signals plus geometry, and inline
candidates from explicit delimiters or conservative relational spans. Exact
source-block text is never replaced. Inline text retains source-relative
character offsets while its image explicitly renders the containing text block.

Every candidate carries exact source/blob/page spans, its raw text, preserved
trailing source label, preceding/following source-block locators when available,
confidence, evidence status, transparent signal counts, and a validated
`RenderedRegion`. Weak relational candidates are `ambiguous` with linked
warnings. Equation-shaped text without complete render geometry is not promoted
and remains an explicit warning. Candidate, warning, renderer, layout,
configuration, and processor identities enter stable result identity.

Configuration hard-bounds pages, input/text blocks, source spans, text,
candidates, inline candidates per block, warnings, candidate text, retained
result size, aggregate rendered PNG bytes/pixels, render padding, and the
ambiguity threshold. Detection and region rendering remain injected protocols.
The current cold contract exposes text PDF
object locators and geometry but not font metrics or drawing-command objects, so
this detector does not invent that unavailable evidence. It makes no symbol
interpretation, transcription-quality, scientific-validation, or human-
acceptance claim and stores no derived result.

**Depends on:** `ING-LAYOUT-01`, `ING-REGION-01`.

**Validation:** focused tests cover the maintained equation fixture, exact
numbered labels, surrounding locators, inline offsets, ambiguous relational
text, prose rejection, absent geometry, rotated rendering, stale layouts,
pre-render candidate limits, stable identity, and immutability; full fixture and
static-analysis suites pass.

### ING-EQUATION-02 — Equation transcription processor (implemented)

The engine-neutral `EquationTranscriptionProcessor` boundary accepts a bounded,
ordered `EquationTranscriptionRequest` over exact equation candidates. A
selection retains the complete validated source `RenderedRegion`; callers can
request LaTeX, MathML, or both in explicit order. Implementations return one
completed, partial, or failed selection result with typed failures and linked
warnings rather than raising away selection-local backend outcomes.

Every proposal is explicitly unaccepted. It retains its exact candidate and
rendered-region identities, format, output text, optional method-described
confidence, processor/backend/configuration provenance, warnings, and ordered
non-overlapping output substrings. Symbol confidence coverage is complete,
partial, or unavailable. Every assessed score below the configured threshold is
`low_confidence`; missing confidence is `unassessed`; both require warning links.
A completed selection requires every requested format and complete assessed
symbol coverage. Partial or failed selections require typed failure and warning
evidence.

Processor/backend versions, configuration version and digest, immutable model
or vocabulary resource identities, requested formats, exact candidate/image
identities, and all resource limits enter the derived cache key. The contract
hard-bounds selections, unique source images, image bytes/pixels, formats,
proposal/symbol text and counts, warnings, resources, aggregate output, identity
size, and retained result size. It defines cache identity but does not add
transcription results to `ExtractionCache` or select a concrete recognition
engine.

**Depends on:** `ING-EQUATION-01`, `ING-CACHE-01`.

**Validation:** focused tests cover LaTeX and MathML proposals, exact retained
PNG evidence, low-confidence marking, unavailable-confidence partial output,
typed failure, cache invalidation by processor/resource/configuration/image,
exact output ranges, image containment and bounds, stable identity,
immutability, and runtime protocol annotations. Proposals make no proofread,
semantic-correctness, scientific-validation, publication, or human-acceptance
claim.

### ING-TABLE-01 — Table candidate detection (implemented)

`DeterministicTableCandidateDetector` consumes an exact extracted document,
page-layout evidence, matching PDF bytes, and bounded page-rule evidence from an
injected inspector. The default lazy `PyMuPdfTableRuleInspector` retains exact
axis-aligned vector line segments, drawing object locators, stroke widths,
processor/backend versions, and an explicit count of unsupported drawing items.
The detector combines those rules with repeated row/column text alignment and
renders only proposed table regions through the injected region renderer.

Each immutable candidate retains one or more ordered page regions, exact source
blocks and spans, row/column band counts, ruled/unruled/mixed boundary evidence,
possible merged-cell block signals, exact PNG regions, confidence, evidence
status, warnings, and nearby source-backed title, caption, note, or continuation
associations. Explicit matching `Table N (continued)` evidence may join adjacent
pages. Merged-cell observations remain warned signals rather than reconstructed
cells. Long prose-like or otherwise weak geometry stays `ambiguous` with linked
warnings.

Configuration hard-bounds source bytes, pages, blocks, text, spans, drawings,
drawing items, rule segments, candidates, regions, associations, warnings,
rendered PNG bytes/pixels, and retained result size. Exact document/layout/rule,
renderer, configuration, and processor identities enter stable result identity.
The stage does not reconstruct rows, columns, headers, cell contents or spans,
and makes no semantic-correctness, scientific-validation, publication, or
human-acceptance claim.

**Depends on:** `ING-LAYOUT-01`, `ING-REGION-01`.

**Validation:** focused tests cover the full maintained PDF matrix (only the
ruled table fixture is promoted) plus generated unruled, explicit multi-page
continuation, merged-cell-signal, prose-like
ambiguous, rotated, stale-layout, wrong-source, pre-render candidate-limit,
render-aggregate-limit, stable-identity, immutability, and protocol cases; full
fixture and static-analysis suites pass.

### ING-TABLE-02 — Table structure reconstruction (implemented)

`DeterministicTableStructureReconstructor` consumes one exact
`TableDetectionResult` and produces immutable, destination-independent columns,
rows, cells, merged-span proposals, and explicit page continuations. Every cell
retains exact native block text and spans when available and always resolves to
the candidate's bounded rendered-region evidence. Multi-block cell text records
the deterministic join method rather than claiming a corrected transcription.

Rule lines are used as proposed boundaries when they form a complete grid;
otherwise bounded native-text geometry supplies midpoint boundaries. Explicit
`Header` evidence proposes header roles. Unresolved headers, unruled or mixed
boundary geometry, empty cells, multiple blocks in one cell, inherited
ambiguity, low confidence,
and merged-span signals remain linked warnings. Explicit multi-page candidates
retain page-local rows and repeated headers separately instead of silently
coalescing cells across pages.

The contract has only `proposed` and `ambiguous` structure states. It preserves
title/caption/note/continuation association identities without folding those
blocks into cells. Configuration hard-bounds candidates, regions, rows,
columns, cells, blocks per cell, spans, associations, continuations, warnings,
text, and retained result size. Exact candidate, warning, configuration, and
processor evidence enters stable identity. The stage writes no files and adds
nothing to the raw extraction cache.

**Depends on:** `ING-TABLE-01`.

**Validation:** focused tests cover the maintained ruled fixture, exact cell
provenance and text, unruled/header ambiguity, merged-column spans, explicit
multi-page continuation with retained repeated headers, deterministic and
configuration-bound identity, pre-reconstruction resource rejection,
immutability, stale identity rejection, and protocol typing. Markdown rendering,
semantic correction, proofread accuracy, scientific validation, publication
suitability, and human acceptance are outside this task.

### ING-FIGURE-01 — Figure and caption extraction (implemented)

`DeterministicFigureCandidateDetector` consumes exact extraction/layout evidence
and matching PDF bytes. Its lazy `PyMuPdfFigureInspector` re-verifies and retains
exact embedded image and optional mask bytes, hashes, media types, source-block
geometry, processor/backend provenance, and bounded PDF drawing-object extents.
Line-only drawing commands remain exact zero-area extents and can form a
positive-area diagram group. Captioned drawing groups are rendered through the
injected bounded region renderer; unassociated drawings remain inspection
evidence rather than silently becoming figures.

Each destination-independent candidate has one or more ordered embedded-image or
rendered-drawing components. Multiple visuals sharing a caption remain separate
subfigure components. Exact `Figure`/`Fig.` captions, `(a)`-style labels, and
explicit `Legend:`/`Key:` blocks are retained as source-backed associations with
confidence. Captionless embedded images stay `ambiguous`. Render selections are
clipped to page bounds, and exact component spans, boxes, artifact hashes,
rendered-region identities, evidence, and warning links enter stable identity.

Configuration hard-bounds source bytes, pages, blocks, text, spans, embedded
asset/mask bytes, drawings/items and grouping comparisons, candidates,
components, association comparisons and outputs, warnings, rendered PNG
bytes/pixels, and retained
result size. The detector
writes no files and adds nothing to the raw extraction cache.

**Depends on:** `ING-REGION-01`, `ING-LAYOUT-01`.

**Validation:** focused tests cover the maintained PDF matrix, exact embedded
image and mask artifacts, caption associations, line-only drawing-command
rendering, source-bounded crops, explicit legends, multi-component subfigures,
captionless ambiguity, table-rule rejection, wrong-source and stale-layout
rejection, pre-render embedded, drawing-group, and association-work limits,
aggregate render limits, deterministic
configuration-bound identity, immutability, stale IDs, and protocol typing.
Figure relevance, pixel semantics, Markdown rendering, proofread accuracy,
scientific validation, publication suitability, and human acceptance are
outside this task.

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
