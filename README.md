# projectkoios-ingestion

Source ingestion and document processing pipeline for Project Koios.

This package coordinates source loaders, document processors, chunk producers,
and index writers through destination-independent interfaces. It does not own
search storage, bibliography management, Markdown projection, or vault writes.

- [Architecture](docs/architecture.md)
- [Contract catalog](docs/contracts/README.md)
- [Legacy aggregate of implemented data contracts](docs/contracts.md)
- [PDF document ingestion ADR](docs/adr.pdf-document-ingestion.md)
- [Document-processing task status](docs/tasks/document-processing-backlog.md)
- [Redistributable PDF fixture matrix](tests/fixtures/pdf/README.md)
- [Redistributable OCR image fixture](tests/fixtures/ocr/README.md)
- [Tesseract installation and adapter setup](docs/tesseract.md)
- [Pix2tex equation-recognition setup](docs/pix2tex.md)

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

Recurring collections use a versioned, path-safe, hash-locked batch plan. Planning is the default and writes nothing; `--apply` is required. Every source byte size, SHA-256 identity, PDF header, and destination is preflighted before the first extraction, source identity is rechecked when read for extraction, existing item output directories are rejected, and the completed JSON summary reports source, document, manifest, artifact, coverage, quality, and warning identities.

```json
{
  "schema_version": 1,
  "items": [
    {
      "source_id": "reference:example2020",
      "pdf_path": "assets/example2020.pdf",
      "output_directory": "example2020",
      "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
      "byte_size": 12345,
      "locator": "assets/example2020.pdf"
    }
  ]
}
```

```bash
koios-ingest-pdf-batch batch.json \
  --source-root ~/projectkoios \
  --output-root ~/projectkoios/.koios/ingestion \
  --cache-root ~/projectkoios/.koios/extraction-cache
koios-ingest-pdf-batch batch.json \
  --source-root ~/projectkoios \
  --output-root ~/projectkoios/.koios/ingestion \
  --cache-root ~/projectkoios/.koios/extraction-cache \
  --apply
```

The batch command is not a multi-document transaction. Preflight prevents known collisions before mutation, and each item retains the single-document publication rollback guarantee. A later runtime failure leaves earlier completed items intact and reports how many completed; retry requires a new plan containing only unfinished items.

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

`koios-detect-pdf-equations-batch` applies this derived stage to an existing raw batch. It accepts the same hash-locked `PdfBatchPlan`, verifies every source and raw-extraction identity before mutation, and is dry-run by default. Explicit `--apply` writes immutable `derived/equations/detection.json` evidence and a compact `retrieval.json` projection under each item directory. The retrieval projection contains native PDF equation text, immediate context, page and source-block locators, rendered-region identities, confidence, warnings, and an explicit `native_text_only` transcription status; it excludes image bytes and does not claim normalized LaTeX. Replaying identical inputs verifies byte-identical artifacts and reports `unchanged`; different or incomplete existing artifacts are preserved and rejected.

```bash
koios-detect-pdf-equations-batch batch.json \
  --source-root ~/projectkoios \
  --ingestion-root ~/projectkoios/.koios/ingestion \
  --cache-root ~/projectkoios/.koios/extraction-cache
koios-detect-pdf-equations-batch batch.json \
  --source-root ~/projectkoios \
  --ingestion-root ~/projectkoios/.koios/ingestion \
  --cache-root ~/projectkoios/.koios/extraction-cache \
  --apply
```

Equation retrieval records are intended as evidence-bearing inputs to a separate search index. Generated assessment prose must not be fed back into the same source corpus. Engine-backed LaTeX or MathML proposals remain a separate optional stage described below.

`koios-enrich-pdf-equations-batch` performs the optional equation-enrichment stage after detection. It groups geometrically adjacent same-line display fragments without crossing detected page columns, rerenders their exact union, retains every raw fragment, creates a control-character-sanitized native-text view, rejects explicit I/O and coordinate-tuple false positives, and invokes a supplied `pix2tex_cli` executable only for non-rejected display assemblies. The executable, backend version, temperature, and every supplied model/configuration/tokenizer resource are hash-bound and rechecked immediately before execution. The package does not install pix2tex or its model files; MathML conversion is available through the optional `.[mathml]` extra.

```bash
koios-enrich-pdf-equations-batch batch.json \
  --source-root ~/projectkoios \
  --ingestion-root ~/projectkoios/.koios/ingestion \
  --cache-root ~/projectkoios/.koios/extraction-cache \
  --pix2tex-executable /path/to/pix2tex_cli \
  --pix2tex-backend-version 0.1.4 \
  --pix2tex-resource model=/path/to/weights.pth \
  --pix2tex-resource image-resizer=/path/to/image_resizer.pth \
  --pix2tex-resource tokenizer=/path/to/tokenizer.json \
  --pix2tex-resource config=/path/to/config.yaml \
  --apply
```

The stage publishes three separate immutable layers: `assembly.json` contains exact grouping and rendered evidence, `recognition.json` contains unaccepted LaTeX/MathML proposals and explicit unavailable-confidence warnings, and `index.json` contains retrieval records partitioned into `primary`, `auxiliary`, and `rejected` tiers. Primary indexing requires a detector-proposed display assembly, sufficient native evidence, structurally bounded LaTeX, successful MathML conversion, source-signal agreement, and no detected prose/repetition anomaly. Ambiguous, inline, incomplete, malformed, or unassessed material remains auxiliary; explicit false positives remain inspectable but rejected. Raw fragments and rendered evidence are never replaced.

Pix2tex is not claimed deterministic. The first bounded result is published immutably with exact processor/resource identity; subsequent identical workflow runs verify the deterministic assembly and linked stored recognition/index artifacts without invoking the stochastic backend again. Changing the executable, model resources, assembly, or policy requires a new artifact location or explicit migration rather than overwrite.

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

The default rule inspector lazily reads axis-aligned PyMuPDF drawing commands and records unsupported drawing-item counts rather than inventing rule evidence. Fill-only commands are counted but not treated as table rules; separate backend-observation and retained-rule bounds allow dense publisher artwork to remain explicit without materializing millions of irrelevant rule objects.
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

On pages whose backend drawing count exceeds the retained-evidence limit, the inspector deterministically retains bounded stroked objects and reports the exact count of ignored fill-only or unusable objects. Separate hard backend limits still fail closed before an unbounded derived artifact is built. Off-page decorative drawing extents are counted as ignored rather than converted into invalid source spans.

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

## Bounded just-in-time processing coordination

`BoundedProcessingCoordinator` invokes one injected `ProcessingProcessor` over
ordered immutable selections. A `ProcessingSelection` may identify exact source
spans, physical page ranges, uniquely resolved printed-page ranges, structure
node IDs, or their explicit union. Resolution creates a `ProcessingWorkItem`
that exposes only selected full pages, spans, nodes, and object IDs; the
coordinator does not pass the complete extracted document or source bytes to the
processor.

Selection-local completed, partial, and failed results retain immutable derived
artifacts, warnings, typed failures, and every retry attempt. Only fully failed
results whose failures are all retryable are retried, up to the configured
bound. Partial output is retained without automatic merging or retry. Unexpected
processor exceptions become generic non-retryable failure evidence without
retaining exception text.

Derived cache keys cover the exact resolved work item, coordinator contract and
configuration, processor/backend versions, processor configuration digest, and
ordered immutable resources. An optional `DerivedProcessingCache` may reuse only
completed or partial selection results; failed results are never published to
it. This cache is separate from raw `ExtractionCache`, and the package provides
no default persistence, engine, model, source-byte loader, or destination
writer.

## Deterministic structured transcription proposals

`DeterministicStructuredTranscriptionComposer` combines one exact document,
structure analysis, equation detection result, table structure result, and
figure detection result. It emits ordered destination-neutral page anchors,
headings, prose, equation candidates, table structures, and figure candidates.
Typed items retain links to their complete upstream objects rather than being
flattened into Markdown or accepted text.

Text normalization is limited to joining exact raw source strings and collapsing
Unicode whitespace with the declared `collapse_unicode_whitespace_v1` method.
Every normalized string retains its exact source strings, raw block IDs, and
source spans. Equation text remains detector-native evidence; tables and figures
remain typed references with no invented textual representation.

Ordering is an explicit proposal based on source geometry, structure reading
order, or a warned uncertain source-order fallback. Duplicate representation and
unrepresented non-text blocks become immutable `TranscriptionOmission` records;
every raw block is covered by an item or omission. Result status is only
`proposed` or `proposed_with_uncertainty`, never proofread accuracy, scientific
validation, publication suitability, or human acceptance. The stage emits no
citekey, vault path, Obsidian syntax, reading status, or destination artifact,
writes no files, and stores nothing in raw `ExtractionCache`.

## Automated clean transcript materialization

`DeterministicCleanTranscriptProjector` creates a separate immutable, automated, unreviewed projection over one complete structured-transcription result and its exact layouts. It preserves each included block's exact raw text, source spans, physical and printed page, proposed order, cleaned text, and typed transformation counts. Excluded repeated margin text, page numbers, and content empty after control-character sanitization retain their exact raw evidence and typed reason. Cleanup is limited to removing soft hyphens, replacing C0 control characters, joining conservative ASCII line-break hyphenations, and collapsing Unicode whitespace; it performs no spelling, symbol, semantic, or scientific correction.

`koios-compose-pdf-transcripts-batch` consumes the same hash-locked `PdfBatchPlan` after raw extraction and equation detection. Dry-run is the default. Explicit `--apply` deterministically runs layout, article structure, equation replay, table detection/reconstruction, figure detection, structured composition, clean projection, and a complete derivation audit. It publishes an all-or-none per-item set containing the clean artifact/text, derivation audit, Proposed reference-evidence projection, and batch manifest. Owner-internal transcript batch manifest schema `2` identifies this five-file artifact-set shape; it is distinct from clean-transcript artifact generation `1` and reference-evidence schema generation `1`. The manifest binds its schema version, every reconstructible intermediate result identity, and all artifact hashes; bulky intermediate table, figure, and full transcription graphs are not materialized. Exact replay verifies all five files byte-for-byte and reports `unchanged`. Legacy four-file schema-`1` sets, incomplete sets, unsafe sets, and different existing sets are preserved and fail closed rather than being relabeled or repaired.

External consumers receive the canonical reference-evidence bytes through an
injected boundary; they do not discover them by constructing this private
workspace layout. The record binds exact source bytes, completed extraction,
`automated_unreviewed` transcript generation `1`, and the recorded derivation
audit while omitting source locators, filenames, paths, and protected text.
Strict parse and verify APIs reject unsupported generations, unknown fields,
noncanonical bytes, incomplete lineage, and source mismatch. This Proposed
projection does not claim independent revalidation, proofreading, extraction
accuracy, scientific validity, or publication suitability; references-side
consumption and cross-repository conformance remain pending.

```bash
koios-compose-pdf-transcripts-batch batch.json \
  --source-root ~/projectkoios/assets/references \
  --ingestion-root ~/projectkoios/.koios/ingestion \
  --cache-root ~/projectkoios/.koios/extraction-cache
koios-compose-pdf-transcripts-batch batch.json \
  --source-root ~/projectkoios/assets/references \
  --ingestion-root ~/projectkoios/.koios/ingestion \
  --cache-root ~/projectkoios/.koios/extraction-cache \
  --apply
```

The plain-text file includes explicit physical/printed page markers and is suitable as source-linked retrieval input, not as a human-proofread edition. Markdown notes and generated relevance assessments remain downstream views and must not replace or feed back into this source corpus.

## Derivation provenance audit

`DerivationAuditValidator` validates one exact source byte string and its `ExtractionResult` together with any supplied OCR, OCR reconciliation, layout, structure, equation, table-detection, table-structure, figure, bounded-processing, structured-transcription, and clean-transcript artifacts. It walks the complete retained dataclass graph under deterministic object and finding bounds, rechecks each artifact's intrinsic contract, verifies source/blob/hash and processor/configuration identities, checks source spans and rendered regions against root-page extents, and requires every supplied transitive dependency to be registered exactly. Clean projections are checked against their registered transcription/layout dependencies, exact root blocks and exclusions, page membership/order, and consolidated text.

The immutable `DerivationAuditReport` is `passed` only when no findings remain. Wrong source bytes or blobs, missing upstream artifacts, mismatched embedded artifacts, orphan block/node/candidate/region references, out-of-range geometry, altered retained content, and missing processor or contract versions produce stable path-addressed findings. `require_valid()` and `validate()` fail closed with `DerivationAuditError`. A passing report verifies software provenance consistency only; it does not establish extraction accuracy, semantic correctness, mathematical correctness, scientific validity, publication suitability, or human acceptance.

Repository routing is documented in `projectkoios-bootstrap/maps/repositories.md`.
