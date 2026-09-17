# Ingestion Data Contracts

## Status

This document specifies the public concepts for PDF document ingestion.
Source, span, block, page, document, warning, manifest, result, extractor,
cache, filesystem-cache, article, textbook, versioned structural analysis,
deterministic article-structure analysis, deterministic PyMuPDF cold extraction,
deterministic page-layout analysis, bounded PDF
region-rendering, bounded OCR request/result contracts, the bounded
Tesseract OCR adapter, deterministic native-text/OCR reconciliation, bounded
equation-candidate detection, engine-neutral equation-transcription contracts,
bounded table-candidate detection, deterministic table-structure
reconstruction, bounded figure-candidate detection, engine-neutral figure-
relevance contracts, bounded JIT processing coordination, and deterministic
structured-transcription proposals are implemented and exported. `RoughChunk`
remains planned until implemented, tested, and
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
letters, decimals, or edition-specific notation. Node identity deliberately
excludes parent/child, warning, and reading-order links so reciprocal hierarchies
can be materialized without circular IDs and inserting earlier evidence does not
renumber unrelated nodes. Complete hierarchy, warning links, and reading order
enter analysis identity.

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

## Equation candidates

Equation contract version 1.0 is a derived evidence contract separate from raw
extraction. `EquationDetectionInput` binds one exact `ExtractedDocument`, one
exact `PageLayoutResult` per page, every raw block/text/span payload relevant to
identity, and a complete `EquationDetectionConfiguration`. Stale source, blob,
page, dimension, rotation, coordinate, kind, block, span, or layout evidence is
rejected.

`DeterministicEquationCandidateDetector` implements the injected
`EquationCandidateDetector` boundary. `detect(document, content)` derives page
layouts through its injected layout processor; `detect_with_layout` accepts an
exact caller-supplied tuple. PDF bytes are passed to the injected
`PageRegionRenderer` only when at least one candidate requires rendering, and
the renderer independently verifies them against the source hash.

Each immutable `EquationCandidate` records:

- display or inline kind, stable ID, exact detection-input/configuration and
  processor identity;
- one exact source text block, ordered source spans, and unmodified raw native
  characters;
- a preserved trailing equation label such as `(3.2)` when present;
- source-relative inline character offsets when applicable;
- exact preceding and following source-block locators on the same page when
  available;
- confidence, transparent matching evidence, `proposed` or `ambiguous` status,
  and warning links; and
- one validated bounded `RenderedRegion` whose selected source box contains all
  candidate geometry. Inline rendering deliberately covers the containing text
  block because the cold contract has no per-character geometry.

Display proposals require bounded relation/operator/variable, strong
mathematical-symbol, or LaTeX-like evidence, with label and centered geometry
only increasing confidence. Inline proposals require explicit `$...$` or
`\(...\)` delimiters or a conservative relational pattern. Long prose and
text merely containing the word “equation” are not signals. Low-confidence
relational candidates remain ambiguous with a linked warning. Equation-shaped
text lacking complete positive-area source geometry is retained only through a
source-backed warning and is not silently rendered as another region.

Configuration hard-bounds pages, all input/text blocks, aggregate source spans
and text, candidate count/text, inline candidates per block, warnings, retained
result size, aggregate rendered PNG bytes/pixels, render padding, and the
ambiguity threshold. Limits and settings enter input and result identity. Result
validation rechecks exact text/offsets, labels, detector evidence, source reading
order, immediate context, warnings,
render provenance/rotation/containment, processor/configuration links, stable
IDs, and retained size. PNG payload bytes are excluded from retained-result
accounting because `RenderedRegion` enforces separate pixel/raster/PNG limits.

The current raw contract retains text PDF object locators and geometry but not
font metrics or PDF drawing-command objects. Detection does not invent them and
does not claim symbol interpretation, semantic correctness, proofread
transcription, scientific validation, publication suitability, or human
acceptance. It writes no files and stores no derived result.

## Equation retrieval projection

Equation-retrieval contract version 1.0 is a compact derived projection over one exact `EquationDetectionResult`. `EquationRetrievalArtifact` binds the source ID and content hash, document ID, detection result and processor/configuration identities, and an ordered tuple of at most 256 unique `EquationRetrievalRecord` values.

Each record retains its candidate ID, display/inline kind, proposed/ambiguous status, detector confidence, physical page index and printed label, exact source block and spans, unchanged native equation text and source label, immediate preceding/following block IDs and unchanged text when available, rendered-region ID/checksum and source geometry, and warning links. `retrieval_text` labels and concatenates only these exact strings for downstream indexing. `transcription_status` is necessarily `native_text_only`; this projection cannot represent inferred or corrected LaTeX or MathML.

The projection excludes rendered PNG bytes while preserving their immutable identities. Consumers requiring visual evidence resolve the record through the full detection artifact. It is not a relevance judgment, mathematical interpretation, proofread transcription, scientific validation, or human acceptance.

## Equation enrichment and index tiers

Equation-enrichment contract version 1.0 preserves four distinct layers. `EquationDetectionResult` remains exact detector evidence. `EquationAssemblyArtifact` groups only geometrically compatible same-page display fragments, retains every candidate ID, detector evidence status, source span, block, raw fragment and label, records every sanitized control character, and owns a newly rendered union region. `EquationRecognitionArtifact` binds a supplied external executable, explicit backend version, temperature, and sorted exact resource hashes to unaccepted LaTeX and derived MathML proposals. `EquationIndexArtifact` contains compact purpose-neutral records without image bytes.

An assembly never rewrites its raw fragments. Its sanitized view replaces non-whitespace control characters only in the derived searchable string and records the replacement count. Inline observations remain auxiliary. Explicit I/O typographic and repeated-fraction coordinate-tuple patterns are rejected from indexing while remaining retained in assembly, recognition-status, and rejected index records.

`Pix2TexCliEquationRecognizer` invokes no shell, stages exact PNGs in a private temporary directory, runs one bounded CPU invocation for all selected display assemblies, enforces timeout and output/diagnostic limits, and parses outputs by exact staged path. The exact launcher hash is retained and rechecked; processor identity uses an additional launcher semantic hash that normalizes only the environment-specific shebang so an otherwise byte-identical installed wrapper remains relocatable. Model/configuration/tokenizer resources are hash-checked at construction and immediately before execution. Pix2tex exposes no calibrated confidence, so every successful output carries `recognition_confidence_unavailable`; a LaTeX proposal remains unaccepted. MathML is a deterministic derivative of that proposal when the optional converter accepts it.

The `primary` retrieval tier requires detector-proposed display evidence, a minimum native-evidence length, bounded balanced LaTeX, successful MathML conversion, agreement with retained native relation/integral/sum/root/partial signals, and no detected prose, repetition, or excessive output. Ambiguous, inline, malformed, incomplete, or otherwise unqualified records are `auxiliary`. Explicit false positives are `rejected`. These tiers control index eligibility only and do not imply mathematical correctness, scientific validation, reference acceptance, or manuscript support.

Because the concrete recognition backend is stochastic, immutable existing recognition is a derived-cache observation rather than a deterministic recomputation claim. A replay rederives and byte-compares the deterministic assembly, verifies source, assembly, processor and index linkages, and reuses the original recognition bytes. Changed resources or policy require a new artifact location or explicit migration.

## Equation transcription proposals

Equation-transcription contract version 1.0 and configuration version 1 define
an engine-neutral `EquationTranscriptionProcessor` protocol. An implementation
exposes `identity_for(request)` and `process(request)`; the package chooses no
recognition engine, model, service, executable, or output destination.

`EquationTranscriptionRequest` contains a non-empty ordered tuple of exact
`EquationTranscriptionSelection` values and an immutable configuration. Each
selection owns one complete `EquationCandidate`, including its original native
text, source spans, context, detection uncertainty, and validated
`RenderedRegion` PNG. Selection validation rechecks source/blob/page identity
and requires the selected image box to contain every candidate source box.
Shared block crops for multiple inline candidates remain representable, while
each candidate may be selected only once per request.

Configuration requests LaTeX, MathML, or both in exact order and records the
low-confidence threshold. It hard-bounds selections, unique images, per-image
and aggregate bytes/pixels, formats, proposals, output characters, symbol
substrings, warnings, failure messages, model/resource identities, aggregate
output/symbol/warning totals, identity size, and retained result size. Its
explicit version and all values enter the configuration digest.

`EquationTranscriptionProposal` is an unaccepted output observation. It retains
exact selection/candidate/region IDs, output format and characters, optional
method/version/scale-described proposal confidence, symbol-confidence coverage,
ordered exact output substrings, warning links, and processor/backend/config
provenance. Substring offsets must be ordered, non-overlapping, in range, and
must reproduce the referenced output characters exactly. Coverage is:

- `complete` only when assessed substrings cover every non-whitespace output
  character;
- `partial` when some output or substring confidence remains unassessed; or
- `unavailable` when the backend supplies no symbol-level confidence.

Each assessed substring below the configured threshold is
`low_confidence`; a missing score is `unassessed`. Both states require warning
links from the substring and containing proposal. There is no accepted,
proofread, corrected, or validated symbol state.

Each selection result is `completed`, `partial`, or `failed`; these are adapter
execution outcomes, not review or acceptance states. Completed output requires
every requested format, proposal confidence, and complete assessed
substring coverage with no failure. Partial output retains at least one
proposal plus typed failure and warning evidence. Failed output retains no
proposal and requires typed failure and warning evidence. Overall status is
derived from all ordered selection statuses. Failures distinguish rejected
input, resource limits, unavailable processors, processor errors, unsupported
formats, invalid output, and incomplete output.

`EquationTranscriptionProcessorIdentity` records processor/backend names and
versions plus ordered immutable model, vocabulary, or other resource identities
using SHA-256 or explicit version strings. The derived cache key includes the
contract/configuration versions, exact ordered candidate and PNG identities,
all requested settings and bounds, and complete processor/backend/resource
identity. The result retains that identity and cache key. The contract defines
cache identity only: it does not put equation transcription into the raw
`ExtractionCache`.

PNG bytes remain directly available through each retained request selection but
are excluded from result-size accounting because separate per-image and
aggregate byte/pixel limits apply. Outputs are proposals from an adapter, not
proofread transcription, semantic interpretation, mathematical correctness,
scientific validation, publication suitability, or human acceptance.

## Table candidates

Table contract version 1.0 is a derived evidence contract separate from both raw
extraction and table-structure reconstruction. `TableDetectionInput` binds one
exact `ExtractedDocument`, one exact `PageLayoutResult` and
`TablePageRuleEvidence` per page, and the complete
`TableDetectionConfiguration`. Stale logical/blob/hash, page, dimension,
rotation, coordinate, raw-block, layout, or rule evidence is rejected.

`DeterministicTableCandidateDetector` implements the injected
`TableCandidateDetector` boundary. It reads the caller's source stream once,
verifies its exact bytes, derives page layouts and rule evidence through injected
processors, then passes isolated streams to the inspector and region renderer;
those adapters independently verify source identity. The
default lazy `PyMuPdfTableRuleInspector` records bounded axis-aligned line and
rectangle-edge segments from PDF drawing commands. Every segment retains exact
source/blob/page identity, orientation, endpoints, stroke width, a drawing-item
locator, stable ID, and inspector/backend provenance. Unsupported or non-axis-
aligned drawing items are not converted into rules; their page-local count is
retained explicitly. The inspector is an adapter, not an OS sandbox, and native
backend memory remains a deployment/source-admission responsibility.

Detection groups repeated source-block row positions and column anchors,
requires configurable minimum row and column support, incorporates nearby
horizontal/vertical rule segments, and keeps long prose-like geometry weak. It
associates only explicit nearby lexical evidence: `Table` titles, `Caption:`
blocks, `Note:`/`Notes:`/`Source:` blocks, and `Table N ... continued` labels.
Adjacent page regions join only with an explicit continuation label, compatible
source label, equal column count, and compatible normalized column anchors.

Each immutable `TableCandidate` records:

- stable input/configuration and detector identity;
- `ruled`, `unruled`, or `mixed` boundary classification;
- `proposed` or `ambiguous` evidence status, source label, confidence,
  transparent evidence and warning links;
- one or more unique page-ordered `TableRegionEvidence` values with exact block
  IDs/spans, source bounding box, row/column band counts, contributing rule IDs,
  possible merged-cell block signals, and validated bounded PNG evidence; and
- source-backed title, caption, note, and continuation associations with exact
  unchanged text, block ID, spans, confidence, and lexical evidence.

Candidate source spans are the ordered table-region block spans; associated
text retains its own spans and is not silently folded into cell evidence. Region
validation re-derives block geometry, row/column counts, merged-row signals,
rule orientation counts, boundary class, prose/title signals, confidence, and
render containment. Candidate validation rechecks ordered pages, aggregate
spans, labels, boundary class, confidence/status, association source blocks,
warning links, and stable identity.

Configuration hard-bounds source bytes, pages, raw/text blocks, text and spans,
drawings and drawing items, page/aggregate rule segments, candidates, regions,
blocks, associations, warnings, retained result size, aggregate rendered PNG
bytes/pixels, row/column minima and tolerances, continuation/association gaps,
render padding, confidence threshold, and prose threshold. All settings enter
input and result identity. PNG bytes are excluded from retained-result size
accounting because separate renderer and aggregate image limits apply.

A single-block row crossing established column anchors is only a
`merged_cell_signal` with a warning. No row, column, header, cell, merged span,
or multi-page cell continuation is reconstructed in this stage. Candidates are
not proofread tables, semantically correct data, scientific validation,
publication-ready output, or human acceptance. The stage writes no files and
stores no derived result in `ExtractionCache`.

## Table structure proposals

Table-structure contract version 1.0 is a derived proposal contract over one
complete exact `TableDetectionResult`. `TableStructureInput` binds that result,
including candidate and detection warning links, to the complete immutable
`TableStructureConfiguration`. It rejects candidate, region, association, row,
column, cell, and predicted-grid counts above configured bounds before
reconstruction.

`DeterministicTableStructureReconstructor` implements the injected
`TableStructureReconstructor` boundary. For every candidate it returns exactly
one `TableStructure` containing:

- contiguous destination-independent `TableColumn` values with normalized
  proposed bounds and all contributing region identities;
- page-local `TableRow` values in one contiguous cross-page reading order, with
  exact source block IDs/spans and retained repeated-header observations;
- a complete non-overlapping `TableCell` grid whose cells record row/column
  position and span, `header`, `body`, or `unknown` role, exact ordered source
  texts/blocks/spans, the deterministic text-join method, and the owning
  candidate-region PNG identity; and
- explicit `TableContinuation` values tied to source-backed continuation
  associations. Page-local rows and repeated headers are retained rather than
  silently coalesced across pages.

A complete vector-rule grid supplies row/column boundaries when available;
otherwise the processor uses native block geometry and records its
rules-or-midpoints method. Explicit source text containing `Header` supplies
header evidence. Candidate merged-row signals become full-column span
proposals, never asserted facts. Unruled or mixed boundary geometry,
unresolved headers, empty cells, multiple blocks in one cell, low candidate
confidence, inherited candidate ambiguity, and merged spans produce linked
warnings. An empty cell
has no invented text and remains grounded in the retained PNG region.
Multi-block text is a newline-joined proposal with exact component strings; it
is not represented as source-native contiguous text.

Structure and cell status is only `proposed` or `ambiguous`; no accepted,
validated, corrected, or human-approved status exists. Stable input/result and
column/row/cell/continuation/structure identities cover the exact detection
result, candidate evidence, configuration, processor version, proposed
geometry, roles, text, spans, rendered-region locators, warnings, and complete
output topology. Configuration hard-bounds candidates, regions, columns, rows,
cells, blocks per cell, source spans, associations, continuations, warnings,
text, and retained result bytes. Exact PNG bytes remain reachable through the
retained detection result but are excluded from retained-result accounting
because their originating renderer/detector contracts already impose aggregate
PNG and pixel limits.

The processor writes no file, performs no Markdown rendering or semantic
correction, claims no proofread accuracy, scientific validity, publication
suitability, or human acceptance, and stores no result in raw
`ExtractionCache`.

## Figure candidates

Figure contract version 1.0 is a derived evidence contract separate from raw
extraction and relevance selection. `FigureDetectionInput` binds one exact
`ExtractedDocument`, one exact `PageLayoutResult` and `FigurePageEvidence` per
page, and a complete `FigureDetectionConfiguration`. Stale source/blob/hash,
page, dimension, rotation, coordinate, raw-block, layout, embedded-asset, or
drawing evidence is rejected.

`DeterministicFigureCandidateDetector` implements the injected
`FigureCandidateDetector` boundary. It verifies matching PDF bytes, obtains
layout and visual evidence through injected processors, detects source-backed
visual/caption groups, and asks the injected `PageRegionRenderer` only to render
promoted drawing-command components. The default lazy
`PyMuPdfFigureInspector` records:

- exact embedded image and optional mask bytes, SHA-256 content identities,
  media types, pixel dimensions, byte lengths, raw image-block IDs/spans, and
  source geometry; and
- bounded PDF drawing-object IDs, ordered page indexes, item counts,
  stroke/fill observations, and exact source extents. Zero-width or zero-height
  line extents are retained and may form a positive-area diagram group.

Inspector evidence is bound to the exact source blob, page geometry,
processor/backend versions, and stable identities. The adapter re-verifies the
cold extractor's image geometry, content hashes, media types, and mask evidence.
Empty or geometrically unusable drawing records are counted rather than
invented as visual commands. PyMuPDF remains a native parser, not an OS sandbox.

Each immutable `FigureCandidate` contains one or more ordered
`FigureComponent` values. An embedded component resolves to one exact
`EmbeddedFigureArtifact`; a drawing component resolves to exact drawing IDs and
a bounded `RenderedRegion` whose source selection contains the component
geometry. Candidate source spans are exactly the ordered component spans, and
the candidate box is their geometric union. Multiple visuals associated with
one caption remain separate ordered components, allowing subfigure structure
without flattening their evidence.

`FigureTextAssociation` retains unchanged source text, block ID, spans,
confidence, and method evidence for explicit `Figure`/`Fig.` captions,
`(a)`-style subfigure labels, and explicitly prefixed `Legend:`/`Key:` blocks.
Caption associations are candidate-wide; subfigure and legend associations
identify one component. Captionless embedded images remain `ambiguous` with
linked warnings. Drawing groups require a nearby explicit figure caption before
promotion; unassociated drawings remain page-inspection evidence with an
informational warning. This prevents a ruled table or decorative line group
from silently becoming a figure candidate.

Configuration hard-bounds source bytes, pages, blocks, text, spans, embedded
asset and mask bytes, drawing objects/items and grouping comparisons,
candidates, components, association comparisons and outputs, warnings,
rendered PNG bytes/pixels, and
retained result size.
Association distance, drawing grouping, minimum drawing geometry, render
padding, legend length, confidence threshold, and all limits enter stable input
and result identity. Render boxes are clipped to exact page bounds. Embedded and
rendered image bytes remain reachable through the result but are excluded from
general retained-size accounting because their dedicated aggregate byte/pixel
limits apply.

The detector writes no files, interprets no image semantics, performs no figure
relevance selection or destination rendering, and makes no proofread,
scientific-validation, publication-suitability, or human-acceptance claim. It
stores no derived result in raw `ExtractionCache`.

## Figure relevance proposals

Figure-relevance contract version 1.0 and configuration version 1 define an
engine-neutral `FigureRelevanceProcessor`. An implementation exposes
`identity_for(request)` and `process(request)`; the package selects no model,
service, prompt, executable, or output destination.

A `FigureRelevanceSelection` retains one complete exact
`FigureDetectionResult` plus the ID of exactly one candidate in that result.
This preserves the selected candidate, alternative candidates, embedded image
and mask bytes, rendered drawing regions, captions, subfigure labels, legends,
source spans, confidence, and detection warnings. `FigureRelevanceRequest`
contains a non-empty ordered tuple of unique selections, one exact nonblank
review question, and the complete immutable configuration. Request identity
covers all of that evidence and configuration.

A completed selection result contains exactly one `FigureRelevanceProposal`.
The proposal records:

- a normalized `FigureRelevanceScore` with explicit method, method version, and
  scale;
- optional independent `FigureRelevanceConfidence` with the same explicit score
  semantics;
- a non-empty rationale and optional exact component/association evidence IDs;
  and
- a level derived deterministically from configured thresholds:
  `proposed_necessary`, `proposed_supporting`, or
  `proposed_not_necessary`.

Those names deliberately preserve proposal status. They are not source facts,
scientific conclusions, publication decisions, or human acceptance. Every
ordered request selection must have exactly one ordered selection result.
Proposed-not-necessary figures remain in both the request and result and cannot
be silently deleted or suppressed by the contract.

Selection-local execution status is `completed`, `partial`, or `failed`.
Partial output requires both a usable proposal and typed failure evidence;
failed output requires typed failure evidence and contains no proposal. Typed
failure kinds distinguish input rejection, stale input, resource limits,
processor unavailability/error, invalid output, and incomplete output. Immutable
warnings
retain severity, evidence, and optional recovery guidance. Missing confidence
is represented by `None` plus an explicit warning, not by an invented score.

`FigureRelevanceProcessorIdentity` records processor/backend names and versions
plus an ordered set of immutable SHA-256 or explicit model, prompt, vocabulary,
or other resource identities. `build_figure_relevance_cache_key` includes the
contract/configuration versions, exact question and ordered selections, complete
configuration, and processor/backend/resource identity. It defines derived
cache identity only and does not write to raw `ExtractionCache`.

Configuration hard-bounds selections, distinct detection results, question and
rationale characters, per-result and aggregate input artifact bytes, rendered
pixels, warnings, failures, evidence, resources, total rationale, and retained
result size. Dedicated upstream figure contracts continue to bound individual
embedded and rendered artifacts; their bytes remain reachable but are excluded
from general retained-size accounting to avoid double counting.

The protocol performs no relevance acceptance, pixel interpretation, semantic
correction, scientific validation, publication selection, destination
rendering, or human approval. It writes no files and stores no derived result.

## Structured transcription proposals

Structured-transcription contract version 1.0, composer version 1, and
configuration version 1 define deterministic destination-neutral composition.
`TranscriptionInput` retains one exact `ExtractedDocument`, complete same-source
`StructureAnalysis`, `EquationDetectionResult`, `TableStructureResult`, and
`FigureDetectionResult`, plus every composition limit. Missing stages are not
silently interpreted as empty; an upstream stage may explicitly supply a valid
empty result.

Input validation requires exact document equality across all derived stages,
complete structure-analysis identity, globally unique raw block IDs, current
structure/candidate block links, same-source in-page finite spans, and bounded
rendered/embedded artifact bytes. A `document_evidence_id` hashes the complete
immutable extracted-document value. The input ID binds that evidence ID, every
upstream result ID, the logical and exact blob identities, and complete
configuration.

`DeterministicStructuredTranscriptionComposer` emits an ordered tuple of
immutable `TranscriptionItem` values:

- one `page_anchor` for every physical page, preserving its printed label;
- `heading` and `prose` items linked to exact structure nodes or raw fallback
  blocks;
- `equation` items linked to complete equation candidates;
- `table` items linked to complete reconstructed table structures; and
- `figure` items linked to complete figure candidates.

Each item records its source-object kind/ID, physical and printed page, source
block IDs/spans, evidence status, confidence, order index/status, warnings, and
bounded evidence. Table and figure items intentionally contain no invented text;
the complete typed objects remain reachable through `TranscriptionInput`.
Equation item text is detector-native raw evidence, not a corrected mathematical
transcription.

Text items preserve every exact source string. Their only normalization joins
ordered source strings with a newline, collapses each Unicode whitespace run to
one ASCII space, and trims leading/trailing whitespace. The method is explicitly
`collapse_unicode_whitespace_v1`. It performs no Unicode compatibility
normalization, spelling correction, symbol interpretation, or semantic rewrite.
Direct construction verifies normalized text against exact source strings.

Ordering is always explicit. `page_anchor`, `proposed_geometric`, and
`proposed_structure` identify their evidence; `uncertain_source_order` requires
a warning when neither geometry nor structure order is available. The composer
uses stable source-object identity as its final tie breaker. Item IDs exclude
global order index so inserting an earlier item does not rename unrelated items;
the complete order and warning links enter result identity.

`TranscriptionOmission` makes duplicate or absent representation explicit.
Reasons distinguish content represented by a typed object, content represented
by an earlier item, source blocks with no text payload, and unrepresented
non-text blocks. Represented omissions link exact replacement item IDs. Every
raw block must be covered by at least one item or omission, and all omission,
warning, source-object, block, and span links are validated.

Result status is only `proposed` or `proposed_with_uncertainty`. Omissions,
warnings, ambiguous evidence, or uncertain ordering select the latter. Neither
status asserts proofread accuracy, semantic correctness, scientific validation,
publication suitability, or human acceptance. The contract contains no citekey,
vault path, Obsidian syntax, reading status, or scientific-acceptance field.

`build_transcription_cache_key` binds the exact input, contract/configuration
versions, composer name/version, normalization method, and every resource limit.
It defines derived identity only; the composer writes no files and stores no
result in raw `ExtractionCache`. Configuration hard-bounds raw blocks, structure
nodes, typed objects, items, omissions, warnings, source spans, per-item and
total text, exact input artifact bytes, and retained result size.

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

## Bounded JIT processing coordination

Processing contract version 1.0, coordinator version 1, and configuration
version 1 define destination-neutral bounded coordination. A
`ProcessingSelection` retains one exact `ExtractedDocument` and at least one of:

- ordered exact source spans;
- inclusive physical page ranges;
- inclusive printed-page ranges whose endpoints resolve uniquely;
- ordered structure node IDs from an exact same-source `StructureAnalysis`; or
- an explicit union of those selectors.

Selection construction rejects wrong blobs, missing pages, stale printed labels,
out-of-page geometry, unknown source objects, stale structure nodes, and stale
node block links. Physical and printed ranges resolve to source order. The
selection identity binds the exact source blob, selector form, selected pages,
selected nodes, and structure-analysis identity. Textbook-specific filenames,
destination selectors, and implicit whole-document selection are not valid
selectors.

`ProcessingRequest` contains a non-empty ordered tuple of unique selections and
a complete immutable `ProcessingConfiguration`. It resolves each selection to
one `ProcessingWorkItem`. A work item exposes only:

- explicitly selected full `ExtractedPage` objects;
- exact selected, page-block, and selected-node source spans;
- exact selected `StructureNode` objects; and
- source-backed input object IDs.

It does not expose the complete `ExtractedDocument` or source bytes to the
processor. The injected processor may already hold application-supplied source
access, but it is responsible for honoring the work-item boundary and must not
dereference `SourceDocument.locator` as implicit authorization for whole-source
work.

`ProcessingProcessor` exposes `identity_for(work_item)` and
`process(work_item)`. `ProcessingProcessorIdentity` records processor/backend
names and versions, the processor's complete configuration digest, and ordered
immutable SHA-256 or explicit model/prompt/resource identities. Identity
resolution must succeed and agree with the processor's declared name/version
before invocation; otherwise coordination fails rather than inventing
provenance.

A processor returns a `ProcessingInvocationResult`. Completed output has no
failures and may be empty for a successfully processed blank selection. Partial
output has both retained `ProcessingDerivedArtifact` values and typed failures.
Failed output has typed failures and no artifacts. Artifacts retain immutable
bytes, media type, SHA-256, exact input object IDs/source spans, and evidence.
Warnings and failures remain work-item-local and source-backed. Output referring
to another source, unselected object, or span outside the selected page/region
becomes an `output_invalid` failure instead of being published.

`ProcessingSelectionResult` preserves every ordered `ProcessingAttempt`, the
resolved work item, processor identity, cache key, final status, and whether
retryable failure exhausted its attempt bound. The coordinator retries only a
fully failed invocation for which every failure is retryable. It never retries
or attempts to merge partial output automatically. Non-retryable failures stop
that selection without stopping later selections. A processor may raise
`ProcessingProcessorError` for typed expected failure; unexpected exceptions
become generic non-retryable `processor_error` evidence without retaining raw
exception text.

`ProcessingResult` preserves one ordered selection result per request selection.
Its execution status is `completed` when all final invocations complete,
`failed` when all fail, and `partial` for every mixed or partial outcome. These
statuses report execution only; they do not assert semantic correctness,
scientific validation, publication suitability, or human acceptance.

`build_derived_processing_cache_key` covers the processing contract and
coordinator versions, exact resolved work item, complete coordination
configuration, processor/backend versions, processor configuration digest, and
ordered immutable resource identities. An optional `DerivedProcessingCache`
may return or store only exact completed or partial selection results. Failed
results are never stored. Cache entries with a wrong key, work item, processor
identity, configuration limits, or failed status are rejected. This derived
cache is distinct from raw `ExtractionCache`; no derived cache implementation or
storage location is selected by the package.

Configuration hard-bounds selection/range/span/node/object counts, attempts,
artifacts and bytes, warnings, failures, messages, evidence, resources, and
retained result size. Requests built from iterables stop after one item beyond
the configured selection bound. Output that exceeds configured limits becomes a
typed non-retryable resource-limit failure. The coordinator chooses no model,
engine, source loader, sandbox, cache persistence, or destination writer and
writes no files.

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
