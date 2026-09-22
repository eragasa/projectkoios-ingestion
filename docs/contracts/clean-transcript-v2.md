# Transcript v2 contract suite

## Contract metadata: clean transcript

| Field | Value |
|---|---|
| Contract ID | `projectkoios.ingestion.clean-transcript` |
| Target version | `0.1.0` |
| Artifact generation | `2` candidate; existing implementation identifiers are not renumbered |
| Status | Proposed |
| Specification revision | Git commit containing this document |
| Owner | `projectkoios-ingestion` |
| Acceptance authority | Project Koios operator after owner and materially affected consumer review |
| Architecture record | [`ADR20260918`](https://github.com/eragasa/projectkoios/blob/main/docs/adr.20260918.evidence-grounded-scientific-rag.md) |
| Task | [`ING-TRANSCRIPT-03`](https://github.com/eragasa/projectkoios-ingestion/issues/2) |
| Predecessor | Legacy clean-transcript contract `1.0` is an owner-internal implementation identifier, not a formal cross-repository release |
| Supersedes | None while proposed |
| Dependencies | Owner-internal extraction, layout, structured-transcription, equation, table, figure, and derivation-audit contracts identified below |
| Consumers | `projectkoios-search`, managed ingestion clients |
| Compatibility | Breaking artifact-generation change relative to transcript v1; migration not yet defined |
| Effective baseline | None while proposed |

## Status

Proposed under
[`ING-TRANSCRIPT-03`](https://github.com/eragasa/projectkoios-ingestion/issues/2).
This document is a planning contract. It does not authorize implementation,
publication, or use of its output as claim-grade evidence.

## Purpose

This suite contains two independently versioned contracts:

- `projectkoios.ingestion.clean-transcript`; and
- `projectkoios.ingestion.transcript-batch-plan`.

The clean-transcript contract governs artifact evidence and transformation
semantics. The batch-plan contract governs reproducible multi-document planning
and publication inputs. A change to one does not automatically change the
other.

Transcript v2 defines a new immutable automated projection over exact PDF
extraction and structured-transcription evidence. Its purpose is to improve
retrieval readability without hiding ambiguity or claiming semantic
correction, proofreading, mathematical interpretation, scientific validation,
or publication suitability.

Transcript v2 supersedes neither raw extraction nor structured transcription.
It does not mutate transcript v1. Each layer remains separately identified and
recoverable.

## Normative scope and conformance

The sections from **Authority and inputs** through **Warnings and status**, plus
**Audit requirements** and the applicable **Acceptance evidence**, are
normative for `projectkoios.ingestion.clean-transcript`. The **Durable batch
planning** section and its metadata are normative only for
`projectkoios.ingestion.transcript-batch-plan`. Purpose, examples, rationale,
and deferred decisions are informative.

The clean-transcript conformance subjects are the projector, immutable artifact
publisher, artifact consumer, and derivation-audit validator. The batch-plan
conformance subjects are the planner, plan parser, and batch publisher. Each
conformance claim MUST identify contract ID, target or accepted version, exact
specification commit, implementation commit, and validation result.

Existing lowercase requirements in the named normative sections express
requirements for these proposed contracts. Before acceptance, they MUST be
converted to the shared capitalized normative vocabulary or mapped explicitly
to conformance tests. Unresolved alternatives or terms such as “conservative”
and “equivalent evidence” block acceptance when they affect observable output.

## Authority and inputs

A projection consumes one exact set of:

- raw extraction and source-byte identity;
- page text, blocks, source spans, and page geometry;
- deterministic page-layout results;
- one complete structured-transcription result;
- equation, table, and figure evidence referenced by that transcription; and
- a versioned cleanup configuration.

Every supplied downstream object must resolve to its exact registered upstream
dependency. Missing, mismatched, duplicated, or ambiguous dependencies fail
closed.

The projector may classify or transform only retained textual evidence. It may
not infer omitted scientific content, repair equations, reinterpret symbols,
or select among competing scientific meanings.

## Version and identity

Transcript v2 uses new contract, configuration, and processor identities. A v2
artifact never reuses a v1 artifact identity or storage location.

The stable artifact identity binds at least:

- the complete structured-transcription identity;
- all page-layout identities;
- ordered included and excluded source records;
- exact raw text and source spans;
- each transformation decision and its evidence;
- warnings and typed classifications;
- page projections and consolidated text;
- contract, configuration, and processor versions; and
- final UTF-8 content length and digest.

Changing any bound field produces a different artifact identity. Replay of the
same inputs and configuration is byte-identical and reports `unchanged` when an
identical immutable publication already exists. Incomplete or different
existing output fails closed.

## Evidence-retention rule

Every source block is represented exactly once as either:

1. an included block retaining exact raw text and source spans; or
2. a typed exclusion retaining the same exact evidence and an exclusion
   decision record.

Transformations attach to included records and never replace the retained raw
text. Classifications that do not justify exclusion remain warnings or
annotations on included evidence.

The audit accounts for all native-text characters through included raw blocks
or retained exclusions. Cleaned-text length is not used as the completeness
measure.

## Allowed cleanup operations

Transcript v2 may retain the bounded v1 operations:

- replacement of disallowed C0 control characters with explicit counts;
- soft-hyphen removal with exact offsets or equivalent source evidence;
- Unicode-whitespace collapse; and
- line-break handling governed by the dehyphenation contract below.

It may not silently perform:

- spelling or grammar correction;
- vocabulary normalization;
- symbol replacement based on inferred meaning;
- equation reconstruction;
- citation correction;
- sentence rewriting; or
- language-model completion.

## Evidence-conservative dehyphenation

A line-ending hyphen is not sufficient evidence for joining tokens.
Dehyphenation produces a typed decision with the source fragments, source
locations, candidate forms, rule identity, supporting evidence, and outcome.

Allowed outcomes are conceptually:

- **join** — bounded evidence supports removal of the line-break hyphen;
- **preserve hyphen** — evidence supports a hyphenated lexical form;
- **preserve break conservatively** — evidence is insufficient or conflicting;
  and
- **not applicable** — the source pattern is not a line-break word split.

A join requires positive evidence from a deterministic, versioned source such
as repeated unbroken use within the same document, an accepted bounded lexical
resource, or another explicitly reviewed rule. Absence from a dictionary is
not evidence for joining. Candidate generation and acceptance remain separate.

Regression evidence must cover the observed erroneous compounds represented by
forms equivalent to:

- `electronicstructure`;
- `tightbinding`;
- `highthroughput`;
- `firstprinciples`;
- `electronphonon`; and
- `stateof`.

The contract does not require silently correcting these strings. It requires
that the responsible source split and decision remain inspectable and that the
known wrong join does not recur under the accepted configuration.

## Page-number classification

Numeric or Roman text is excluded as a page number only when bounded evidence
supports that role.

Sufficient evidence is one of:

1. an exact relationship to a retained printed-page label; or
2. recurring page-margin geometry plus a consistent cross-page sequence under
   a versioned rule.

A margin position alone is insufficient. A short numeric string alone is
insufficient. Plot-axis labels, table values, equation labels, figure labels,
and scientific measurements remain included unless independently classified by
an owning structured-evidence contract.

Each page-number exclusion retains:

- raw text and source spans;
- physical and printed page identity;
- geometry;
- classification method and version;
- sequence or printed-label evidence; and
- confidence or ambiguity state without representing a heuristic score as a
  probability.

All previously observed plot-axis misclassifications are mandatory negative
fixtures. Acceptance requires zero known plot-axis labels excluded as page
numbers.

## Publisher front matter

Publisher-originated cover, notice, masthead, licensing, and citation material
receives a typed classification. Classification does not automatically imply
exclusion.

A record may be excluded only under an explicit configuration policy that
retains its exact raw evidence and classification. Bibliographic or rights
information needed to identify the source must remain recoverable even when it
is omitted from consolidated retrieval text.

The initial taxonomy and policy require review against the observed corpus.
Unrecognized front matter remains included with a warning rather than being
silently discarded.

## Private-use glyphs

Every Unicode private-use code point produces a finding bound to exact block,
page, text, source-span, and code-point evidence.

The default action is retention with a warning. Replacement requires a
separately versioned mapping supported by exact rendered or source evidence.
Font appearance, semantic meaning, and mathematical identity must not be
invented from a private-use code point alone.

## Warnings and status

The artifact status remains `AUTOMATED_UNREVIEWED`. Warnings are deterministic,
bounded, and included in stable identity. At minimum they cover:

- ambiguous dehyphenation;
- unresolved page-label classification;
- unrecognized publisher front matter;
- private-use glyphs;
- source/control transformations; and
- any retained v1 limitation still applicable to v2.

A manual spot check may create separate review evidence. It does not change the
artifact into a human-proofread edition.

## Contract metadata: transcript batch plan

| Field | Value |
|---|---|
| Contract ID | `projectkoios.ingestion.transcript-batch-plan` |
| Target version | `0.1.0` |
| Status | Proposed |
| Specification revision | Git commit containing this document |
| Owner | `projectkoios-ingestion` |
| Acceptance authority | Project Koios operator after ingestion and reference-boundary review |
| Architecture record | [`ADR20260918`](https://github.com/eragasa/projectkoios/blob/main/docs/adr.20260918.evidence-grounded-scientific-rag.md) |
| Task | [`ING-TRANSCRIPT-03`](https://github.com/eragasa/projectkoios-ingestion/issues/2) |
| Predecessor | None registered; the temporary local plan is operational evidence, not a contract |
| Supersedes | None while proposed |
| Dependencies | `projectkoios.ingestion.clean-transcript@0.1.0` plus owner-internal acquisition, source, extraction, equation, and transcription identities |
| Consumers | `projectkoios-ingestion`, verified acquisition-manifest producers |
| Compatibility | Unknown until deterministic regeneration and legacy-plan migration are demonstrated |
| Effective baseline | None while proposed |

## Durable batch planning

Recovery MUST NOT depend on a plan stored only in a temporary directory. A
batch plan is either:

- an immutable managed operational artifact under the owner-defined `.koios`
  workspace; or
- deterministically regenerated from verified acquisition, source, extraction,
  equation, and transcription metadata.

The planner binds source identities and hashes, expected predecessor artifact
identities, requested processor/configuration versions, destinations, and plan
version. Dry run is the default. Apply requires explicit intent and publishes
atomically.

Plans contain repository-relative or logical artifact identities in public
records. Machine paths and protected source details remain in private managed
state.

The implementation candidate uses transcript-batch-plan schema `1`. Each item
binds the source byte identity, safe relative source and ingestion paths,
raw-extraction artifact hash and manifest identity, equation-detection artifact
hash and result identity, complete cleanup configuration, processor version,
and generation-specific destination. The generation-1 command and artifacts
remain unchanged. Generation 2 is published only under
`derived/transcription/generation-2/`; dry-run remains the default, and explicit
`--apply` is required for durable-plan or artifact publication. This
implementation detail does not change the Proposed contract status.

## Audit requirements

The derivation audit verifies:

- exact source-byte and extraction lineage;
- registration of every transitive dependency;
- exact raw text, spans, page membership, and ordering;
- one-time accounting of every source block;
- transformation and classification evidence;
- consolidated-text reconstruction;
- page and artifact identity contracts; and
- manifest and persisted-file hashes.

Audit success establishes internal derivation consistency only.

## Acceptance evidence

Before transcript v2 can gate claim-grade indexing, the implementation must
demonstrate:

- zero known plot-axis labels classified as page numbers;
- passing regressions for all known compound-word failures;
- explicit findings for every observed private-use glyph;
- complete native-character accounting;
- passing clean-inclusive audits for every document in the evaluation corpus;
- byte-identical deterministic replay;
- fail-closed behavior for incomplete or different immutable output;
- full unit, integration, lint, type, build, and isolated-install validation;
  and
- recorded manual spot checks that retain the automated-unreviewed claim.

These checks do not establish extraction accuracy, scientific correctness,
human proofreading, canonical bibliography status, or publication readiness.

## Deferred decisions

This contract does not select:

- a human editorial workflow;
- a semantic language model for correction;
- a claim-level scientific verification method;
- retrieval chunk size;
- an embedding model; or
- publication or manuscript policy.
