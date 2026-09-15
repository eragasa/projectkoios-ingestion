# Ingestion Data Contracts

## Status

This document specifies the public concepts for PDF document ingestion.
Source, span, block, page, document, warning, manifest, result, extractor,
cache, filesystem-cache, article, textbook, structural-analysis, deterministic
PyMuPDF cold extraction, and bounded PDF region-rendering contracts are
implemented and exported. `RoughChunk`, OCR, and the general
`ProcessingSelection`/`ProcessingResult` JIT coordination specializations remain
planned until implemented, tested, and exported; that deferred status does not
include the implemented bounded region renderer.

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
- dimensions and coordinate system. PyMuPDF pages report unrotated crop-box
  width and height matching their extracted coordinates;
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
optional native PDF object ID,
and an optional `SourceSpan` for an internal physical-page destination. It does
not prescribe a generated heading, filename, or consumer navigation target.

It does not contain destination paths, Markdown filenames, search scores, or
vault links.

## `StructureNode`

Describes a source-backed structural hypothesis.

Fields include:

- stable node ID;
- node kind;
- source label and title;
- ordered source spans;
- parent and ordered child IDs;
- evidence type;
- confidence;
- warning references.

Node kinds may include front matter, part, chapter, section, subsection,
prose, equation, figure, table, example, problem set, problem, bibliography,
and unknown.

Numbers remain strings because source numbering may contain Roman numerals,
letters, decimals, or edition-specific notation.

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

PNG signatures, dimensions, byte length, content hashes, and complete region
identity are validated by the contract. Stable region identity excludes source
locators and printed page labels. Printed labels are retained exactly as
returned by the backend, with an empty label represented as unavailable.
PyMuPDF page rotation changes display orientation and therefore output pixel
orientation, but the requested and effective source boxes remain in the
declared unrotated coordinate system. For the recorded affine `(a, b, c, d, e,
f)`, a PNG pixel-edge coordinate `(x, y)` maps to source point
`(x*a + y*c + e, x*b + y*d + f)`. The effective box encloses the four mapped
PNG boundary corners; it may extend beyond the requested box because scaled
display coordinates are rounded outward to integer pixel boundaries. Rendering
writes no files and performs no OCR,
region detection, layout analysis, semantic interpretation, storage
publication, or model calls.

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
