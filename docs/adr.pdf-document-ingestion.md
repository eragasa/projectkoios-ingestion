# ADR: Output-independent PDF document ingestion

## Status

Accepted

## Context

Project Koios needs reusable ingestion of PDF articles and textbooks. A source
may contain native text, scans, bookmarks, printed page labels, equations,
figures, examples, and problems. Downstream applications may index the result,
render Markdown, build another document format, or request expensive processing
only for selected material.

Coupling PDF extraction directly to Markdown or an Obsidian vault would make
source processing destination-specific. Eager OCR, image rendering, and
semantic cleanup would also impose substantial computation and storage on
users who need only part of a document.

The accepted repository-establishment ADR places chunking algorithms, source
loaders, concrete search indices, and domain workflow logic outside this
repository. PDF support must either preserve those boundaries or supersede them
explicitly.

## Decision

If accepted, PDF document ingestion will follow these rules.

1. `PdfArticleIngester` and `PdfTextbookIngester` return normalized,
   destination-independent extraction objects rather than Markdown notes.

2. The initial deterministic PDF adapter will use PyMuPDF behind an optional
   dependency boundary. Importing the base ingestion package will not require
   PyMuPDF.

3. Cold extraction will preserve an application-supplied logical source ID,
   an exact source-blob hash, page order, page labels, text and layout blocks,
   bookmarks, image references, coordinates, extraction quality, and
   structured warnings. Logical identity will not be derived from source
   bytes.

4. Structural analysis will represent chapters, sections, equations, figures,
   examples, and problems as source-backed hypotheses with evidence and
   confidence. It will not prescribe destination filenames.

5. OCR, page-region rendering, and semantic processing will be available as
   bounded JIT processing through injected protocols. They will not run for an
   entire corpus by default.

6. Raw extraction and derived processing results will have separate cache
   identities. A processor or prompt change will not invalidate deterministic
   raw extraction.

7. Every extracted or derived object will retain transitive provenance to the
   logical source ID, exact source-blob hash, physical PDF page, printed page
   label when available, and source coordinates when available.

8. The ingestion package may coordinate an injected chunk producer and writer.
   Search-specific chunking algorithms, indices, embeddings, and ranking remain
   outside this repository under the existing accepted boundary.

9. Persisted manifests and provenance will use versioned, language-independent
   contracts. Internal implementation objects will prefer immutable
   dataclasses.

10. Test fixtures will be generated or redistributable. Private user document
    collections may be used for local acceptance testing but will not be product
    fixtures or encoded configuration.

## Alternatives considered

### Return Markdown notes directly

Rejected because it couples source extraction to one projection format and
mixes machine-reproducible extraction with human-owned content.

### Eagerly run semantic cleanup for every document

Rejected because cost scales with the complete corpus even when only a small
selection is used. JIT processing permits bounded work and reusable caching.

### Render every PDF page

Rejected because full-page image materialization can exceed the storage used by
source PDFs. Embedded assets and selected regions can be materialized on demand.

### Put textbook chunking in ingestion immediately

Rejected for this decision because it would silently contradict the accepted
repository boundary. A later ADR may move a general document-chunking algorithm
here with explicit dependency and ownership consequences.

### Require a dedicated graph or vector database

Rejected as an ingestion decision. Storage and retrieval are consumer concerns,
and ingestion contracts must remain usable with files, SQLite, in-memory
implementations, or future systems.

## Consequences

### Positive

- Extraction can serve search, Markdown, APIs, and other destinations.
- Expensive work is bounded by actual use.
- Source provenance survives every supported transformation.
- Optional dependencies remain isolated.
- User naming and layout policies remain configurable outside ingestion.
- Cached raw extraction can be reused after downstream processor changes.

### Negative

- Consumers need an additional projection step.
- Provenance and versioned manifests increase model complexity.
- Structural inference requires explicit confidence and correction mechanisms.
- JIT processing introduces cache and partial-failure behavior.
- Search-specific chunks cannot be fully specified by this repository alone.

## Acceptance criteria

Before this ADR can be accepted, an implementation plan must demonstrate:

- public extraction and provenance contracts;
- lazy optional loading of PyMuPDF;
- deterministic extraction from a generated text PDF;
- stable identities across equivalent reruns;
- physical and printed page provenance;
- warnings for an image-only or low-text page;
- article and textbook structure fixtures;
- a bounded processing selection;
- separate raw and derived cache keys;
- no source mutation;
- no imports from Obsidian, search storage, or model-provider packages.

## Amendment: logical and blob identity

The initial foundational implementation incorrectly derived `source_id` from
the SHA-256 digest of source bytes. The accepted model separates an
application-supplied logical source ID from a content-derived source-blob ID.
SHA-256 identifies exact bytes for integrity and cache invalidation; it does
not define the permanent logical identity of a document.

This correction produced contract version 2.0 before the PDF adapter was
implemented. The additive 2.1 contract adds immutable table-of-contents entries
with source-local bookmark identity and optional physical-page destinations;
2.0 constructors remain source-compatible because the new tuple defaults to
empty. Contract 2.2 adds a trailing defaulted `ExtractedPage.rotation_degrees`
field, preserving positional page construction while retaining native rotation
evidence needed by bounded layout processing.

## Implementation status

The initial PyMuPDF cold extractor is implemented behind the optional `pdf`
extra. It emits extractor-native ordered text blocks, content-addressed image
and mask references with media types, bounding boxes in a declared unrotated
crop-box coordinate system, page labels, PDF bookmarks/table-of-contents
evidence, source hashes, stable object identities, and structured low-text
warnings. It keeps native block order without making a layout claim and records
the installed PyMuPDF version in extractor/cache identity.
The CLI can project raw page text and the complete versioned extraction
contract into explicitly selected artifact directories. It refuses to
overwrite existing artifacts and rolls back artifacts created by an invocation
when an ordinary publication error is handled. A process or machine crash can
still leave a partial multi-file publication because portable filesystems do
not provide an atomic transaction across the requested paths.

The filesystem raw-extraction cache is implemented with versioned canonical
JSON envelopes, complete identity and contract validation, atomic single-entry
publication, and optional CLI reuse. Deterministic page-layout analysis is
implemented as a separate bounded derivation with stable processor and
configuration identity, source-backed text-block references, geometry evidence,
heuristic confidence, and explicit ambiguity; it never replaces or reorders raw
blocks. Removing the old cold multicolumn warning changed the extractor adapter
version from 1 to 2. Additive page-rotation evidence changed the extraction
contract from 2.1 to 2.2; both identities invalidate earlier raw cache entries.
Selected-region
rendering is implemented as an explicit non-empty ordered selection contract and
lazy PyMuPDF adapter
that returns validated in-memory PNG evidence under deterministic
pre-allocation limits. Bounded OCR request/result contracts and an injected
processor protocol are implemented over that exact rendered evidence. They use
canonical semantic language tags, pre-execution backend/resource identities,
source-verified native-text coexistence references, optional method-described
confidence, and explicit completed/partial/failed outcomes, including blank
success. A caller may now explicitly inject the lazy `TesseractOCRProcessor`,
which runs one bounded no-shell POSIX subprocess per selected PNG, snapshots and
hashes exact traineddata resources, and strictly maps TSV evidence without
merging native text. A separate deterministic reconciliation processor now
requires exact native page/layout provenance, retains both original streams,
and proposes bounded duplicate, disagreement, native-only, and OCR-only
relationships. It leaves ambiguity and disagreements explicit and makes no
semantic-correction, scientific-validation, or human-acceptance claim. Derived
OCR/reconciliation storage and semantic cleanup remain future work. A separate
bounded article-structure processor now consumes exact page-layout evidence and
proposes source-backed front matter, heading hierarchy, bibliography
observations, and appendices with explicit heading/reading-order confidence.
The raw contract currently exposes no font metrics, so the processor does not
invent them. Its hierarchy is neither semantic validation nor human acceptance.
A separate bounded equation-candidate detector now retains native display/inline
text, offsets, labels, surrounding block locators, and exact rendered-region
evidence. Weak signals or missing geometry remain explicit warnings; unavailable
font and drawing-command observations are not invented. A candidate makes no
symbol-interpretation or transcription-quality claim. Selected candidates may
flow to an engine-neutral equation-transcription boundary that retains exact PNG
evidence and returns bounded LaTeX/MathML proposals, confidence coverage,
warnings, typed failures, complete processor/model provenance, and derived cache
identity. Low and unavailable confidence stay explicit; no proposal is called
proofread, mathematically correct, scientifically validated, or accepted. A
separate bounded table-candidate detector now combines exact layout evidence,
lazily inspected axis-aligned PDF rules, source-backed title/caption/note and
continuation locators, and exact rendered regions. Multi-page links require
explicit continuation evidence; merged-cell observations remain warnings rather
than reconstructed cells. A candidate makes no table-structure, semantic-
correctness, publication, scientific-validation, or acceptance claim. A
separate deterministic table-structure processor now consumes that complete
exact candidate result and proposes bounded columns, page-local rows, complete
cell coverage, header roles, ambiguous merged spans, and explicit page
continuations. Each cell retains exact source blocks/spans or the original
rendered-region evidence; continued-page rows and repeated headers are not
silently coalesced. Unruled, mixed-boundary, or unresolved geometry stays
warning-linked. The processor emits no Markdown and makes no proofread,
semantic-correctness, scientific-validation, publication, or human-acceptance
claim. A separate bounded figure detector now re-verifies exact embedded image
and mask artifacts, retains bounded drawing-object evidence, and renders only
captioned drawing-command diagram groups. Explicit source captions, subfigure
labels, and legends remain confidence-bearing proposals. Captionless images stay
ambiguous, and unassociated drawing groups are not silently treated as figures.
The stage makes no pixel-semantic, relevance, publication, scientific-
validation, or acceptance claim. Selected candidates may flow to an engine-
neutral figure-relevance boundary that retains the complete exact detection
result and review question, then returns scored proposals, rationales, explicit
confidence, warnings, typed failures, and processor/model resource identity.
Proposed-not-necessary figures remain inspectable and cannot be suppressed by
the result contract. No proposal is scientific validation, publication
selection, or human acceptance. A bounded generic JIT coordinator now resolves
explicit source-span, physical/printed-page, structure-node, or union selections
into work items that expose only selected evidence. It invokes one injected
processor per ordered selection, retains completed/partial/failed attempts,
retries only wholly retryable failed invocations within a configured bound, and
computes processor/resource-bound derived cache keys. Failed results are not
eligible for the optional injected derived cache, and no derived result enters
raw `ExtractionCache`. The coordinator selects no engine, model, source loader,
cache persistence, or destination writer. The absence or failure of OCR
execution must not be hidden by treating raw text extraction as a proofread
transcription.

## Relationship to existing decision

This ADR extends `adr.20260629.establish-ingestion-repo.md`. It does not
supersede that ADR's chunking-algorithm or search-index ownership boundary.
