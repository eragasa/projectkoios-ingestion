# projectkoios-ingestion

Source ingestion and document processing pipeline for Project Koios.

This package coordinates source loaders, document processors, chunk producers,
and index writers through destination-independent interfaces. It does not own
search storage, bibliography management, Markdown projection, or vault writes.

- [Architecture](docs/architecture.md)
- [Public data contracts](docs/contracts.md)
- [PDF document ingestion ADR](docs/adr.pdf-document-ingestion.md)
- [Document-processing task status](docs/tasks/document-processing-backlog.md)
- [Redistributable PDF fixture matrix](tests/fixtures/pdf/README.md)
- [Redistributable OCR image fixture](tests/fixtures/ocr/README.md)
- [Tesseract installation and adapter setup](docs/tesseract.md)

The optional deterministic PDF adapter is installed with `.[pdf]` and exposed
through `koios-ingest-pdf`. It writes a versioned extraction contract and,
optionally, one raw text artifact per physical page. `--cache-root` enables the
filesystem extraction cache: a compatible hit returns the exact cached result
without invoking PDF extraction, and a miss is cached before artifacts are
published. Existing artifacts are never overwritten. A handled publication
error removes files and directories created by that invocation; because
filesystems do not provide a portable multi-file transaction, a process or
machine crash can leave a partial artifact set that must be inspected and
removed before retrying.

```bash
koios-ingest-pdf article.pdf \
  --source-id reference:example2020 \
  --cache-root .koios/extraction-cache \
  --output .koios/example2020/extraction.json \
  --raw-text-directory .koios/example2020/pages
```

Cache entries use canonical JSON envelopes at
`CACHE_ROOT/v1/<key-prefix>/<sha256(cache-key)>.json`. Key identity covers the
cache format, extraction contract, logical and exact blob source identities,
extractor and installed backend versions, and extraction-affecting
configuration. Envelopes record source, processor, configuration, manifest,
and payload identities for diagnosis. The diagnostic source locator is not a
key field under the accepted source contract, so a hit preserves the locator
recorded by the cached extraction. Malformed or excessively nested JSON,
invalid Unicode, truncated data, unrepresentable numeric values, unsupported
versions, and identity inconsistency are reported as corruption; none is treated
as an ordinary miss. Invalid keys or results supplied to `put` raise
`ValueError` before cache-root mutation.

Each cache write flushes an exclusive same-directory temporary file, atomically
publishes it only when the destination is absent, and syncs the directory. An
existing valid entry for the exact key is accepted; an unrelated or corrupt
regular file is preserved and reported instead of being overwritten.
Concurrent writers therefore accept the first complete valid entry. Uncatchable
termination can leave an ignored temporary, and a filesystem that does not
honor durable sync can lose the newest publication.

This cache backend requires POSIX descriptor-relative filesystem operations,
`O_DIRECTORY`, `O_NOFOLLOW`, `O_NONBLOCK`, and no-follow `stat` and hard-link
support. It fails
closed with `ExtractionCacheSafetyError` before touching the cache root when
those capabilities are unavailable; uncached extraction remains portable. The
cache does not provide eviction, migration, distributed locking, automatic
corruption repair, or cache-root symlink support.

PDF parsing runs in the CLI process and reads the complete source into memory.
PyMuPDF is a complex native parser, not a security sandbox. Applications that
accept untrusted PDFs should enforce input and resource limits and use an
operating-system isolation boundary when their threat model requires one.

## Bounded PDF region rendering

`PyMuPdfRegionRenderer` lazily uses the same optional `pdf` extra. It requires a
non-empty ordered set of explicit full-page or bounding-box selections and
returns immutable `RenderedRegion` values containing PNG bytes and complete
source, geometry, configuration, content-hash, processor, and backend evidence.
Coordinates are unrotated crop-box points from top left; page rotation is
applied only when mapping that exact source box into the displayed raster.
Fractional clips are rounded outward to the backend pixel grid. Each result
records both the requested box and effective source footprint, plus an affine
mapping from PNG pixel-edge coordinates back to source points.

```python
from io import BytesIO
from pathlib import Path
from projectkoios.ingestion import (
    PageRegionSelection,
    PyMuPdfRegionRenderer,
    SourceDocument,
)

payload = Path("article.pdf").read_bytes()
source = SourceDocument.from_bytes(
    payload,
    source_id="reference:example2020",
    media_type="application/pdf",
    locator="article.pdf",
)
selection = PageRegionSelection.for_bounding_box(
    source, 0, (72.0, 72.0, 360.0, 216.0)
)
region = PyMuPdfRegionRenderer(resolution_dpi=144).render(
    source, BytesIO(payload), (selection,)
)[0]
```

Output is opaque RGB on white by default; `RegionColorMode.GRAYSCALE` is also
supported. Defaults limit requests to 256 selections and each raster to 16,384
pixels per dimension, 25,000,000 pixels, and 100,000,000 uncompressed bytes.
The complete set of unique selections is also limited to 25,000,000 pixels and
100,000,000 uncompressed raster bytes. Iterable consumption is capped at the
selection limit plus one, and all raster limits are checked before the first
pixmap allocation. Full-page rendering must use
`PageRegionSelection.for_full_page`; there is no render-all operation. The
adapter does not perform OCR, region detection, interpretation, file writes, or
storage publication.

Region rendering follows the repository-wide PDF trust boundary: callers must
admit bounded source sizes before invocation and apply process isolation where
their threat model requires it. A shared ingestion source-admission policy must
be established before accepting untrusted or unbounded documents; this adapter
does not introduce a renderer-only source-size policy. Stable PNG bytes are
verified for repeated execution with one concrete installed PyMuPDF build and
are not claimed across different native builds that report the same version.

## Bounded OCR

Tesseract is an external executable, not a Python package dependency. Install it
before using the concrete adapter:

```bash
# macOS
brew install tesseract

# Debian or Ubuntu
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-eng
```

Homebrew includes only `eng` and `osd`; `brew install tesseract-lang` adds the
optional language collection. See the [Tesseract setup guide](docs/tesseract.md)
for resource discovery, verification, adapter configuration, and the optional
real-engine smoke test.

Bounded OCR is exposed through immutable contracts and an `OCRProcessor`
protocol. An `OCRRequest` preserves ordered exact `RenderedRegion` evidence and
explicitly
configures canonical semantic language tags, token/line output, and all
resource limits. Native-text coexistence references are verified against the
same extracted source page. Each output has in-image pixel geometry and a
validated source box mapped through the region affine, warning links, and an
optional adapter score with an explicit method/version/scale. A completed empty
result represents a successfully processed blank region. Per-selection
completed, partial, and failed statuses preserve mixed outcomes without merging
or replacing native text. `build_ocr_cache_key` covers the contract, complete
ordered input, configuration, processor/backend identity, and ordered
language-resource identities without storing OCR data in `ExtractionCache`.

`TesseractOCRProcessor` is the first concrete OCR adapter. It requires explicit
`TesseractLanguageBinding` values mapping semantic request languages to exact
traineddata files. Before execution it resolves `tesseract --version`, hashes
the bounded normalized version report, executable, and each requested resource,
and includes those engine/resource identities plus a digest of all adapter
behavior/resource settings in the OCR cache identity. Missing executables,
mappings, or resources become typed selection failures rather than imports or
silent fallback.

The adapter invokes no shell and uses one bounded POSIX subprocess per explicit
selection. Exact PNG and traineddata snapshots are staged only in a private
temporary directory; timeout, standard-output/error, individual resource, and
aggregate resource limits are enforced. Strict UTF-8 Tesseract TSV is mapped to
requested token/line evidence and normalized, method-described confidence.
Blank output completes successfully; usable output from a nonzero invocation is
partial and linked to typed warning/failure evidence. Native text remains a
separate stream. The adapter does not install Tesseract, retain raw diagnostics,
write durable artifacts, cache OCR results, reconcile streams, or publish a
destination format. A subprocess is not an operating-system sandbox and the
adapter does not impose a native-process memory limit; deployments accepting
untrusted images or traineddata must add an appropriate OS isolation boundary.

`DeterministicOCRReconciler` is the separate, injected reconciliation stage. It
accepts one exact OCR selection and the matching native page/layout evidence,
then performs bounded deterministic text-and-source-geometry matching. Its
immutable result preserves exact native and OCR streams while proposing
one-to-one duplicates, unresolved disagreements, native-only evidence, OCR-only
evidence, and an optional merged order. Ambiguous near-ties remain unmatched.
A consumer can select either original stream; disagreement proposals choose no
text. This stage does not perform semantic correction, certify accuracy or
scientific validity, record human acceptance, publish files, or add derived
results to `ExtractionCache`.

## Deterministic article structure

`DeterministicArticleStructureAnalyzer` derives a bounded, destination-neutral
article hierarchy from an exact `ExtractedDocument` and its deterministic page
layouts. It proposes title, explicit authors, abstract, keywords, numbered or
conservative known-name sections, subsections, bibliography observations, and
appendices while retaining exact source spans and block IDs. Heading level and
reading order carry separate confidence; parent/child links are reciprocal and
acyclic. Matching table-of-contents evidence can strengthen one unique heading.

Fallback titles and layout uncertainty remain warnings. Bibliography entries
are typed observations and cannot be represented as accepted or validated
references. The current raw contract exposes no font metrics, so the analyzer
does not invent them. The result is not proofread transcription, semantic or
scientific validation, human acceptance, a citekey decision, or a destination
format, and it is not stored in `ExtractionCache`.

## Bounded equation candidates

`DeterministicEquationCandidateDetector` proposes display and inline
equation-shaped evidence from exact extraction and page-layout inputs. Each
candidate retains unchanged native characters, source spans and inline offsets,
numbered labels, immediate source-block context, transparent confidence, and a
validated bounded `RenderedRegion`. Inline crops explicitly cover their
containing text block because character-level geometry is unavailable.

The detector uses explicit delimiters and conservative relation/operator/symbol
signals; prose containing only the word “equation” is not promoted. Weak
relational candidates are ambiguous with warnings, and equation-shaped text
without geometry is not rendered. The raw contract currently has no font or
PDF drawing-command observations, so the detector does not invent them. Results
make no symbol-interpretation, proofread-transcription, scientific-validation,
human-acceptance, or publication claim and are not stored in `ExtractionCache`.

## Engine-neutral equation transcription

`EquationTranscriptionProcessor` is the injected boundary for proposing LaTeX,
MathML, or both from selected equation images. Requests retain complete
`EquationCandidate` and `RenderedRegion` evidence. Results retain explicit
processor/backend/configuration versions, immutable model-resource identities,
typed partial/failure outcomes, warnings, and a complete derived cache key.

Output substrings carry method-described confidence. Scores below the configured
threshold are `low_confidence`; missing scores are `unassessed`; both require
warning links. Complete output requires assessed substring coverage for every
requested format. No concrete recognition engine is selected, no result is put
in the raw extraction cache, and no proposal is described as proofread,
semantically correct, scientifically validated, publication-ready, accepted, or
human-approved.

## Bounded table candidates

`DeterministicTableCandidateDetector` proposes ruled, unruled, mixed-boundary,
and explicit multi-page table regions from exact native blocks, layout evidence,
PDF vector-rule observations, and bounded PNG crops. Candidates retain source
blocks/spans, row and column bands, possible merged-cell signals, confidence,
warnings, and nearby title, caption, note, and continuation locators.

The default rule inspector lazily reads axis-aligned PyMuPDF drawing commands and
records unsupported drawing-item counts rather than inventing rule evidence.
Long prose-like or weak candidates remain ambiguous. Merged-cell signals remain
warnings, not reconstructed cells. This detection stage neither reconstructs
table structure nor claims semantic correctness, scientific validation,
publication suitability, human acceptance,
or destination formatting, and its results are not stored in
`ExtractionCache`.

## Deterministic table structure

`DeterministicTableStructureReconstructor` consumes an exact table-detection
result and proposes destination-independent columns, page-local rows, cells,
column spans, header roles, and explicit page continuations. Cells retain exact
ordered native block text and source spans when available and always retain the
original candidate-region PNG identity. Repeated headers on continued pages are
marked but not discarded or silently merged.

Complete vector grids provide proposed boundaries; otherwise native-text
geometry provides transparent midpoint boundaries. Unruled or mixed boundary
geometry, unresolved headers, empty or multi-block cells, low confidence,
inherited ambiguity, and
merged spans remain warnings. The model has no accepted state, does not alter
source text, writes no files, and makes no proofread, semantic-correctness,
scientific-validation, publication, Markdown, or human-acceptance claim.

## Bounded figure candidates

`DeterministicFigureCandidateDetector` consumes exact extraction and layout
evidence plus the matching PDF bytes. The lazy `PyMuPdfFigureInspector` retains
exact embedded image and mask bytes with their content hashes and media types,
as well as bounded PDF drawing-object locators and source geometry. Embedded
images remain embedded artifacts; captioned diagrams composed from drawing
commands are rendered through the injected `PageRegionRenderer`.

Candidates may contain one or more ordered components for subfigures. Explicit
`Figure`/`Fig.` captions, `(a)`-style subfigure labels, and `Legend:`/`Key:` text
remain exact source-backed associations with confidence. Captionless embedded
images remain ambiguous. Drawing groups without explicit figure captions are
retained as inspection evidence but are not promoted, preventing ruled tables
from silently becoming figures. Render selections are clipped to page bounds,
and every artifact records exact source regions, hashes, processor/backend
identity, confidence, and warning links.

The stage does not interpret pixels, infer scientific meaning, select relevant
figures, render Markdown, publish files, or claim proofread accuracy,
publication suitability, scientific validation, or human acceptance. Derived
figure results are not stored in `ExtractionCache`.

## Engine-neutral figure relevance

`FigureRelevanceProcessor` is the injected boundary for proposing how relevant
selected figures are to one exact review question. Each selection retains its
complete `FigureDetectionResult`, so embedded bytes, rendered regions, source
associations, alternative candidates, and uncertainty remain inspectable.
Processors return normalized method-described scores, optional independent
confidence, exact evidence references, and a non-empty rationale. Unavailable
confidence remains `None` and requires an explicit warning.

Levels are explicitly `proposed_necessary`, `proposed_supporting`, or
`proposed_not_necessary`; none is source fact, scientific validation, or human
acceptance. Completed, partial, and failed selection-local outcomes preserve
warnings and typed failures. Every requested selection must have one ordered
result, including proposed-not-necessary figures, so the protocol cannot delete
or silently suppress them.

Request identity covers the exact question, ordered complete figure evidence,
thresholds, and all resource limits. Derived cache identity additionally covers
processor/backend versions and ordered immutable model, prompt, vocabulary, or
other resource identities. The package chooses no model, service, executable,
or destination, writes no files, and does not put relevance results in raw
`ExtractionCache`.

Routing and role split live in `projectkoios-bootstrap/docs/agent-charter.md`.
