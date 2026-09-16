# Ingestion Data Contracts

## Status

This document specifies the public concepts for PDF document ingestion.
Source, span, block, page, document, warning, manifest, result, extractor,
cache, filesystem-cache, article, textbook, versioned structural analysis,
deterministic article-structure analysis, deterministic PyMuPDF cold extraction,
deterministic page-layout analysis, bounded PDF
region-rendering, bounded OCR request/result contracts, the bounded
Tesseract OCR adapter, and deterministic native-text/OCR reconciliation are
implemented and exported. `RoughChunk` and the
general `ProcessingSelection`/`ProcessingResult`
JIT coordination specializations remain planned until implemented, tested, and
exported.

## Contract Principles

- Internal domain objects are immutable dataclasses where practical.
- Persisted forms use explicit, versioned, language-independent schemas.
- Paths and destination names are not document identities.
- Source labels are preserved as strings rather than normalized destructively.
- Optional fields represent unavailable evidence; they do not invent values.
- Every derived object carries or resolves transitively to provenance.

## `SourceDocument`

Identifies source bytes supplied for ingestion.

Required information:

- stable logical source ID supplied by the application;
- exact source-blob ID;
- media type;
- content hash and hash algorithm for the source blob;
- byte length;
- source locator suitable for diagnostics;
- discovery time or source revision when supplied.

The logical source ID remains stable across byte-level revisions. The blob ID
identifies one exact byte representation and is derived from its content hash.
The source locator may be a path, URI, or application-defined value; it is
neither identity.

## `SourceSpan`

Locates evidence within a source document.

PDF spans contain:

- logical source ID;
- exact source-blob ID;
- zero- or one-based physical page under an explicitly declared convention;
- printed page label when available;
- source block or object ID;
- bounding box and coordinate system when available. PyMuPDF cold extraction
  uses points relative to the top-left of the unrotated page crop box, with
  positive x to the right and positive y downward;
- optional character or token offsets within the block.

A derived object may refer to multiple ordered spans, including spans that
cross page boundaries.

## `ExtractedBlock`

Represents a raw source-backed unit such as text, an image reference, or a
drawing region.

Required information:

- stable block ID;
- block kind;
- ordered source spans;
- raw or normalized payload appropriate to the kind;
- content-addressed asset identity and media type for image blocks, plus a
  separate content-addressed mask identity and media type when present;
- extraction method;
- extraction confidence;
- warning references.

Normalization must not make the original extractor payload irrecoverable when
that payload is needed to verify mathematical or technical content.

## `ExtractedPage`

Contains the ordered extraction result for one physical PDF page:

- physical page index;
- printed page label;
- dimensions, coordinate system, and clockwise page rotation in degrees.
  PyMuPDF pages report unrotated crop-box width and height matching their
  extracted coordinates and rotation in `{0, 90, 180, 270}`;
- blocks in extractor-native source order;
- image and drawing references;
- extraction quality metrics;
- page-level warnings.

Page order is physical source order. Printed labels may be non-numeric.

## `ExtractedDocument`

The destination-independent result of deterministic source extraction:

- contract version;
- source document;
- document metadata as observed in the source;
- ordered pages;
- immutable bookmarks and table-of-contents evidence;
- extraction manifest reference;
- document-level warnings.

Contract version 2.1 adds `table_of_contents` as an additive trailing tuple that
defaults to empty. Its placement preserves the positional field order of 2.0
`ExtractedDocument` construction. Each entry records a stable entry ID, exact
logical and blob source identity, source hierarchy level, source title,
optional native PDF object ID, and an optional `SourceSpan` for an internal
physical-page destination. Contract version 2.2 adds trailing, defaulted
`ExtractedPage.rotation_degrees` evidence while preserving positional
construction. It does not prescribe a generated heading, filename, or consumer
navigation target.

It does not contain destination paths, Markdown filenames, search scores, or
vault links.

## `StructureNode` and `StructureAnalysis`

Structure contract version 1.0 represents source-backed hypotheses without an
acceptance or validation state. `StructureNode` records:

- a stable ID derived from kind, exact ordered source spans and source-block
  IDs, evidence, title/label, heading observations, confidence, and evidence
  status;
- a kind including document, front matter, title, author, abstract, keywords,
  section, subsection, appendix, bibliography, and bibliography entry;
- reciprocal parent and ordered child IDs;
- optional source label and title;
- separate overall, heading-level, and reading-order confidence;
- optional non-negative heading level and contiguous reading order;
- transparent immutable evidence and warning links; and
- `observed`, `proposed`, or `uncertain` evidence status. No accepted,
  scientifically validated, or human-approved status exists. Bibliography-entry
  nodes are required to remain `observed`.

Numbers remain strings because source numbering may contain Roman numerals,
letters, decimals, or edition-specific notation. Node identity deliberately excludes parent/child, warning, and reading-order
links so reciprocal hierarchies can be materialized without circular IDs and
inserting earlier evidence does not renumber unrelated nodes. Complete hierarchy,
warning links, and reading order enter analysis identity.

`StructureAnalysis.create` binds nodes to an exact logical/blob source, ordered
layout-result identities, processor name/version, and configuration digest.
It validates stable IDs, exact source provenance, immutable tuples, aggregate
bounds, unique contiguous reading order, unique warnings, warning links,
reciprocal parent/child links, and acyclic hierarchy. The original minimal
`StructureAnalysis(nodes=...)` form remains available for injected legacy
analyzers but cannot claim processor/layout identity.

## Deterministic article structure

`DeterministicArticleStructureAnalyzer` implements `ArticleStructureAnalyzer`.
`analyze(document)` produces and consumes exact deterministic page-layout
results; `analyze_with_layout(document, layouts)` accepts caller-supplied exact
results and rejects stale source, page, dimensions, rotation, coordinate, raw
block, kind, or span evidence.

The processor preserves layout-proposed text order and retains excluded text
after it in extractor-native order. It proposes a source-backed document root,
optional grouped front matter, metadata-correlated or explicitly warned
fallback title, explicitly prefixed authors, abstract and bounded abstract body,
keywords, numbered and conservative known-name sections, subsections,
bibliography, observed bibliography entries, and appendices. Matching PDF
bookmarks/table-of-contents entries strengthen heading evidence and level only
when exactly one source heading matches; they do not create unanchored text.
Every content node has exact source spans, source-block IDs, contiguous reading
order, and method-described confidence. Hierarchy links are reciprocal.

Configuration places hard ceilings on pages, text blocks/characters, nodes,
warnings, heading length, abstract blocks, and bibliography entries; all limits
and the fallback-title geometry threshold enter configuration and analysis
identity. Layout ambiguity, missing/fallback titles, empty bibliographies, and
missing text remain explicit warnings. The current raw extraction contract does
not retain font metrics, so the analyzer does not invent font evidence; its
bounded evidence is bookmarks/table of contents, numbering, explicit labels,
known headings, source geometry, and layout order.

The output is a proposal, not semantic correction, proofread transcription,
scientific validation, citation approval, or human acceptance. Bibliography
entries are source observations, never approved references or final citekeys.
The analyzer writes no files and stores no derived result.

## `ExtractedArticle`

Specializes an extracted document with article-oriented structure, including
bibliographic metadata candidates, abstract, sections, figures, equations, and
references. Bibliographic candidates are observations, not approved catalog
entries or final citekeys.

## `ExtractedTextbook`

Specializes an extracted document with textbook-oriented structure, including
front matter, parts, chapters, sections, examples, problem sets, figures,
equations, appendices, and index candidates.

It does not prescribe filenames for those units.

## `RoughChunk`

Represents destination-independent content prepared for a consumer-provided
index writer.

Fields include:

- stable chunk ID;
- ordered source spans;
- text or typed payload;
- structural ancestry;
- content kind;
- parent, previous, and next IDs when known;
- extraction confidence;
- warning references.

A rough chunk must not split an indivisible typed object such as an equation,
caption, or problem merely to satisfy a token target. Search-specific vectors,
scores, and ranking features are not part of this contract.

## `PageLayoutResult`

`DeterministicLayoutProcessor` returns one immutable `PageLayoutResult` for
each analyzed `ExtractedPage`. Layout contract version 1.0 is separate from raw
extraction contract 2.2. Processor version 2 contains the repaired identity and
conservative ambiguity semantics. A result records:

- stable result and exact source-page IDs;
- logical source ID, exact source-blob ID and SHA-256, physical page index,
  dimensions, printed label, coordinate system, and page rotation;
- every raw page block as a non-owning kind-and-source-span reference in
  extractor-native order;
- text-block references projected exactly from those raw references, plus every
  non-text block ID excluded from text analysis;
- proposed text-block order and explicit reason/evidence for every text block
  excluded because usable positive-area geometry is unavailable;
- one exclusive group membership for every ordered block, with group kind,
  union bounding box, transparent evidence, heuristic confidence, and warning
  links;
- page hypothesis, page evidence, ambiguity warnings, processor name/version,
  and complete configuration digest.

Direct construction validates finite in-page geometry, exact source/page/span
identity, unique raw/reference/order/exclusion/group/warning IDs, complete text
coverage by either order or documented exclusion, exclusive group membership,
group bounding boxes and stable IDs, warning cross-links and IDs, processor
identity, and stable result identity. Group identity includes confidence and
ordered warning links. The public factory rejects supplied text/non-text
classifications or spans that differ from `ExtractedPage.blocks`. Tuple-valued
contracts must actually be immutable tuples. Signed zero in layout geometry is
canonicalized before it enters identities; non-finite geometry is rejected.

The default bounded geometry heuristic admits at most 1,024 total raw blocks,
512 text blocks, 2,048 total source spans, 4,096 characters per identity field,
and 1,000,000 aggregate identity characters per page. These limits are checked
before provenance validation, tuple/set construction, or pair analysis. It
uses horizontal gaps and actual block-level vertical concurrency plus minimum
flow extent to propose one or two columns. A spanning-heading candidate must be
sufficiently wide, lie above both columns, intersect both column extents, and
cross the gutter. Multiple or offset wide candidates remain ambiguous.
Separated bottom text is ordered after main flow only with the low-confidence
group kind `footnote_candidate` and always carries a warning because identical
geometry may be a footer or final paragraph. Narrow asymmetric side groups, block
overlap, touching or weak separation, sparse or staggered groups, bridging top
blocks, and nonzero page rotation remain explicit low-confidence ambiguity
hypotheses. Unsupported coordinate systems are rejected. Confidence is a
bounded heuristic score, not a probability, scientific validation result, or
proofread-transcription measure. Thresholds and resource bounds are versioned
configuration identity.

The processor neither owns nor mutates raw blocks. Images and other non-text
blocks remain available in `ExtractedPage.blocks` and cannot enter text-layout
groups. Text-kind blocks without string text payloads are explicitly excluded;
a page with text but no analyzable geometry is ambiguous with zero confidence,
not empty. Known limits are deliberate: analysis is page-local, proposes at most
two confident columns, uses extracted ink boxes rather than typography or PDF
drawing commands, and cannot semantically distinguish columns from tables or a
true footnote from other separated bottom text. More complex geometry becomes
an imperfect low-confidence fallback and requires inspection. The processor
performs no OCR, semantic section recognition, table reconstruction, equation
or figure interpretation, document-wide ordering, model call, publication, or
derived-result caching.

## `PageRegionSelection` and `RenderedRegion`

`PageRegionSelection` requests exactly one zero-based physical PDF page. It
carries logical and exact blob source identity and explicitly distinguishes a
full page from a bounding box. A bounded selection uses finite, non-negative,
strictly ordered, positive-area coordinates in
`pymupdf_unrotated_cropbox_points_top_left`; boxes outside the actual page crop
box are invalid. `PyMuPdfRegionRenderer.render` requires a non-empty iterable of
these selections, preserves requested order, and provides no implicit
whole-document operation.

`RegionRenderConfiguration` records positive integer DPI, opaque RGB or
opaque grayscale output on white, and pre-allocation limits. Defaults are 144
DPI, 256 requested selections, 16,384 pixels per dimension, 25,000,000 pixels,
and 100,000,000 uncompressed raster bytes per region. Aggregate unique-region
limits default to 25,000,000 pixels and 100,000,000 uncompressed raster bytes.
All participate in its stable digest. The renderer consumes no more than the
selection limit plus one iterable items, then computes every per-region and
aggregate raster limit before asking PyMuPDF to allocate the first pixmap.

Each immutable `RenderedRegion` directly carries PNG bytes and records:

- logical source ID, exact source-blob ID, and source content SHA-256;
- zero-based physical page and optional printed page label;
- the exact requested source bounding box and whether full-page selection
  produced it;
- the effective source footprint after outward pixel-grid rounding, page
  rotation, and scaling, plus the page rotation and affine mapping from PNG
  pixel-edge coordinates to unrotated source points;
- the declared unrotated crop-box coordinate system and pixel-rounding
  convention;
- DPI, color mode, and opaque alpha behavior;
- PNG media type, byte length, pixel dimensions, and content SHA-256;
- region ID, configuration digest, renderer identity/version, and PyMuPDF
  backend identity/version.

PNG signatures, ordered chunk structure, chunk CRCs, required IHDR/IDAT/IEND
content, bounded decompression size, dimensions, color format, byte length,
content hashes, immutable byte type, and complete region identity are validated
by the contract. Stable region identity excludes source locators and printed
page labels. Printed labels are retained exactly as returned by the backend,
with an empty label represented as unavailable.
PyMuPDF page rotation changes display orientation and therefore output pixel
orientation, but the requested and effective source boxes remain in the
declared unrotated coordinate system. For the recorded affine `(a, b, c, d, e,
f)`, a PNG pixel-edge coordinate `(x, y)` maps to source point
`(x*a + y*c + e, x*b + y*d + f)`. The effective box encloses the four mapped
PNG boundary corners; it may extend beyond the requested box because scaled
display coordinates are rounded outward to integer pixel boundaries. Rendering writes no files and performs no OCR, region detection, layout
analysis, semantic interpretation, storage publication, or model calls.

## OCR requests and results

`OCRRequest` is a non-empty ordered tuple of explicit `OCRSelection` values.
Each selection owns an `OCRPageImage` that nests one exact, already validated
`RenderedRegion`; it therefore retains the logical source ID, exact blob/hash,
page and region identity, requested and effective source footprints, PNG
identity/bytes/dimensions, coordinate system, rotation, and complete
pixel-to-source affine mapping without a lossy image alias. A selection may
also retain ordered `OCRNativeTextBlockReference` values projected from a
supplied `ExtractedPage`. The public factory verifies that every named block
exists, is text, and has spans matching the same logical source, exact blob, and
physical page as the rendered region. These references state only that native
and OCR evidence coexist on the page; they never replace, merge, or reconcile
the native stream.

`OCRConfiguration` declares ordered canonical semantic language tags using the
supported BCP 47 syntax; `und` is allowed, backend resource names are not, and
registry/resource existence is deliberately not inferred. It also declares
token, line, or token-and-line output and deterministic positive limits for
selection and distinct-image counts, per-image and aggregate pixels/PNG bytes,
language count and length, identity lengths, per-selection and aggregate
tokens/lines/text/warnings, warning evidence/message sizes, and aggregate
result size. A request's aggregate warning capacity must permit at least one
typed failure warning per selection, so every-selection failure remains
representable. Every choice and limit enters its configuration digest and cache
identity. Tuple fields require actual immutable tuples; booleans are not
accepted as integers, invalid Unicode and duplicate IDs fail, and request
iterables are consumed only through the configured selection limit plus one.
Cheap counts are checked before output traversal. Hard implementation ceilings
prevent caller configuration from disabling those bounds. Result size is
accounted incrementally before stable-ID canonicalization; retained request
metadata is counted, while input PNG payload bytes are excluded because their
per-image and aggregate byte limits are enforced separately.

`OCRToken` and `OCRLine` retain text, contiguous order, warning links, strict
positive-area pixel boxes, and mapped source boxes. Confidence is optional. If
present, `OCRConfidence` includes the adapter-reported finite value in `[0, 1]`
plus its method, method version, and scale. Scores from different methods are
not assumed comparable and are not probabilities, proofread accuracy, or
scientific validation. Pixel boxes must lie within the exact PNG. Source boxes
are calculated from all four pixel-box corners through the region affine and
are revalidated in `pymupdf_unrotated_cropbox_points_top_left`, including when
the PNG orientation arose from page rotation. In combined output, line IDs
retain ordered token membership and each token names its line order; membership
must be complete, exclusive, and geometrically contained. Output identities
cover text, both coordinates, confidence, warning links, order/membership,
input/configuration identity, and processor/backend identity.

Each `OCRSelectionResult` is completed, partial, or failed. Completed means the
processor ran successfully and cannot claim a failure; an empty completed
result truthfully represents a blank region with no recognized text. When a
completed result has output, it must contain every stream required by the
requested output mode. Partial results retain usable output and require both
typed failure and linked warning evidence. Failed results require the same
explicit failure/warning evidence and cannot contain tokens or lines. `OCRResult`
preserves request order and is completed only when every selection completed,
failed only when all failed, and partial otherwise. Direct construction
revalidates stable identities, source/image/configuration links, output order,
warning/failure links, token membership, coordinates, processor/backend
identity, and aggregate limits.

`build_ocr_cache_key` is the cache identity boundary for a future derived OCR
cache. It includes OCR contract version, ordered exact image/source identities,
selection and native-block evidence, language/output configuration, all
behavior/resource settings, and an `OCRProcessorIdentity` available before
execution. That descriptor records processor and backend name/version plus an
ordered one-to-one binding from every requested semantic language tag to the
selected backend resource name and immutable SHA-256 or explicit versioned
resource identity. `OCRProcessor.identity_for(request)` exposes this boundary
to callers. The contract does not change `ExtractionCache` or store OCR
results. It does not itself select an adapter, engine, executable, model,
Markdown format, destination, publication, or native/OCR reconciliation policy.

## Native-text/OCR reconciliation

`DeterministicOCRReconciler` implements the injected `OCRReconciler` boundary.
Reconciliation contract version 1.0 consumes one exact `OCRSelectionResult` and,
when its selection names native blocks, requires the exact `ExtractedPage` and
`PageLayoutResult` from which those references came. It rejects stale source,
blob, page, rotation, coordinate, dimension, raw-block, kind, or source-span
evidence rather than guessing how to align it.

The result preserves three independently selectable views:

- `native_stream`, containing exact selected native block text and source spans
  in the layout-proposed order, with layout exclusions conservatively retained
  after ordered blocks in extractor-native order;
- `ocr_stream`, containing the exact ordered `OCRLine` objects from the selected
  OCR result; and
- `proposed_merged_stream`, containing a complete one-time coverage of every
  native line segment and OCR line as duplicate, disagreement, native-only, or
  OCR-only evidence.

Native blocks remain the original native view. `OCRNativeLineSegment` is only a
bounded line projection used for comparison; it retains its block identity,
line index, exact text, normalized comparison text, order, and available union
source box. The reconciler applies Unicode NFKC, case folding, and whitespace
collapse only to matching. It never overwrites either original text payload.
Exact normalized text is a duplicate candidate when known source geometry does
not contradict it. Non-identical text can become a disagreement candidate only
when source boxes meet the configured overlap threshold and bounded string
similarity meets its threshold. Matching is deterministic and one-to-one.
Near-tied candidates are left unmatched with an ambiguity warning rather than
resolved by arbitrary selection.

A duplicate proposal preserves native text. A disagreement has no proposed
text and links a specific warning, forcing the consumer to choose or review the
alternatives. Unmatched native items preserve native text. Unmatched OCR items
preserve OCR text and are appended in OCR engine order after the layout-ordered
native sequence with an explicit ordering-uncertainty warning; this is a
conservative proposal, not a semantic reading-order claim. Completed blank OCR,
native-only, OCR-only, partial, failed, rotated, and
ambiguous inputs remain explicitly representable. Original OCR status,
failures, warnings, tokens, image bytes, and processor identity remain
transitively available through the retained input.

Configuration records geometry, similarity, and ambiguity thresholds plus hard
bounds for native blocks/segments, OCR lines, candidate pairs, text-comparison
work, per-comparison text, retained text, warnings, and retained result size.
Those settings enter input and result identity. Limits are checked before
quadratic matching; token-only
nonblank OCR output is rejected because it cannot provide the required line
stream. Result validation checks exact evidence retention, contiguous orders,
one-to-one links, geometry and similarity evidence, warning links, merged
coverage, proposed text, configuration identity, and stable IDs. Input PNG bytes
are excluded from retained-result accounting because OCR request limits already
bound them.

Reconciliation is evidence organization only. It does not claim semantic
correction, proofread accuracy, scientific validation, human acceptance, or
publication suitability. It writes no files, stores no derived result, changes
no `ExtractionCache` entry, and performs no OCR or model call.

## Tesseract OCR adapter

`TesseractOCRProcessor` implements `OCRProcessor` as a lazy external-process
adapter; importing the package does not import, bundle, or install Tesseract.
Installation and explicit resource discovery are documented in
[`tesseract.md`](tesseract.md). Construction requires immutable
`TesseractLanguageBinding` values that map each
supported semantic language tag to one safe backend resource name and an
explicit traineddata path. There is no implicit language-name conversion or
fallback. A request missing a mapping produces `UNSUPPORTED_LANGUAGE`; a
missing executable or resource produces `PROCESSOR_UNAVAILABLE`.

`identity_for` resolves the executable without a shell, invokes bounded
`tesseract --version`, hashes its bounded normalized version/dependency/capability
report and the executable bytes, and incrementally hashes every requested
traineddata file under individual and aggregate limits. `OCRProcessorIdentity`
records those engine identities and ordered semantic-language/resource-name/
SHA-256 bindings. The effective processor version additionally incorporates the
complete `TesseractAdapterConfiguration` digest: timeout, stdout/stderr capture
bounds,
traineddata bounds, page segmentation mode, and optional engine mode. Only
OCR-producing page-segmentation modes that do not require an implicit OSD
resource are accepted. Thus engine, resource, mapping, and adapter-setting
changes alter the OCR cache key.
Before OCR invocation, the executable is rehashed and each traineddata file is
copied into a private temporary snapshot while its hash is recomputed; a changed
executable or resource fails closed.

Processing uses one no-shell POSIX subprocess per explicit selection, a minimal
locale/thread environment, a new process session, exact PNG input with its
declared render DPI, staged traineddata, and TSV output. The adapter
concurrently drains stdout and stderr,
kills the process group on timeout or capture overflow, and removes temporary
inputs/resources when the request ends. Raw stderr is deliberately not retained
in result identity. Missing execution facilities, timeouts, output overflow,
nonzero exits, malformed output, and contract-limit violations become typed
selection-local warning/failure evidence. Usable strict TSV from a nonzero or
timed-out process may be retained as partial output; unusable output fails.

Tesseract level-5 TSV words become ordered tokens. Words are grouped by page,
block, paragraph, and line identifiers; line text joins trimmed word text with a
single space and line geometry is the union of member word boxes. TSV word
confidence is normalized from `[0, 100]` to `[0, 1]` with an explicit method and
scale; line confidence is present only when every member has a score and is the
arithmetic mean of normalized word scores. These scores are backend evidence,
not probabilities or proofread accuracy. Blank valid TSV is completed empty.
Native-text references are never removed, replaced, or merged. The adapter does
not publish files, store derived results, or implement reconciliation. Its
subprocess/session boundary is not an operating-system sandbox and does not cap
native-process memory; callers admitting untrusted PNG or traineddata bytes must
supply deployment-level sandboxing and resource controls.

## `ProcessingSelection`

Requests bounded JIT processing. A selection may identify:

- source spans;
- physical or printed page ranges;
- structure node IDs;
- an application-supplied union of selections.

Textbook-specific filenames and destination selectors are not valid source
selections.

## `ProcessingResult`

Records a derivation over selected extracted content:

- result ID and contract version;
- input object IDs and source spans;
- processor identity, version, and configuration digest;
- derived objects;
- warnings;
- cache identity;
- completion status.

Partial results distinguish completed selections from failed selections.

## `IngestionWarning`

A structured warning contains:

- stable warning ID;
- warning code;
- severity;
- human-readable message;
- affected object IDs and source spans;
- evidence or metric values;
- suggested recovery action when known.

Warning codes are stable API. Human-readable wording may evolve.

## `IngestionManifest`

The manifest makes a run inspectable and reproducible:

- manifest and contract versions;
- logical source identity, exact blob identity, and content hash;
- extractor identity and version;
- processor identities and versions;
- normalized configuration digests;
- created object IDs;
- warning IDs;
- cache keys;
- start, completion, and status information.

Timestamps do not participate in deterministic content identity. The PyMuPDF
adapter records both its adapter version and the installed PyMuPDF backend
version as extractor identity, so a backend upgrade changes the raw extraction
cache key.

## Stable Identity

Stable IDs use content and source-local evidence. A conceptual form is:

```text
source ID = stable logical identity supplied by the application
blob ID = hash(exact source bytes)
block ID = hash(source ID, blob ID, page, source object evidence)
node ID = hash(source ID, blob ID, node kind, source spans, source label)
chunk ID = hash(source ID, blob ID, source block IDs, content kind)
TOC entry ID = hash(source ID, blob ID, native outline evidence, title, target)
result ID = hash(input IDs, processor version, configuration digest)
rendered region ID = hash(source IDs, page, exact selection, configuration,
                          renderer/backend identity, PNG hash)
```

A new byte representation changes the blob ID and extraction cache without
forcing a logical document rename. The exact encoding requires a separate
schema decision. IDs must not depend on a destination filename or a
process-global sequence number.

## Provenance Invariants

1. An extracted block resolves directly to source spans.
2. A structure node resolves to the blocks or spans supporting it.
3. A rough chunk resolves to its ordered source blocks or spans.
4. A processing result resolves to both its inputs and original source spans.
5. Confidence and warnings remain attached through derivation.
6. A consumer may serialize provenance without importing a PDF library.

## Serialization and Versioning

Persisted contracts include a schema or contract version. Readers reject
unsupported major versions and tolerate documented additive minor fields.

Binary assets are referenced by content identity and media type rather than
embedded in JSON. A transparency mask is a separate content reference when
PyMuPDF reports one. A storage adapter decides whether asset bytes live in
files, an object store, or another local representation.

The filesystem extraction cache uses cache format version 1 canonical JSON
envelopes. The logical extraction key includes cache and contract versions,
logical source ID, exact source-blob ID, extractor/installed-backend identity,
and configuration digest. The envelope repeats diagnostic identity evidence
and hashes the complete serialized result. Readers reject unsupported formats,
malformed data, hash/key disagreement, invalid stable IDs, and inconsistent
source or span provenance instead of interpreting those states as misses.
Publication never replaces an existing final path: a valid exact-key entry is
accepted, while an unrelated or corrupt regular file is preserved and reported.
The filesystem implementation requires POSIX descriptor-relative and no-follow
filesystem capabilities and fails closed before cache-root access when they are
unavailable. Excessive JSON nesting and non-finite or unrepresentable numeric
values read from entries are corruption errors; analogous invalid caller keys or
results raise `ValueError` before cache-root mutation.

## Consumer Responsibilities

Consumers decide:

- destination naming and paths;
- bibliography approval and citekeys;
- search indexing and ranking;
- Markdown or other rendering;
- human review and promotion;
- retention and deletion policy.

A consumer must not represent inferred structure as source fact without
retaining the inference confidence and evidence.
