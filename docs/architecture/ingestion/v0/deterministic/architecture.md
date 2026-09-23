# Deterministic Ingestion v0 Architecture

## Architectural Model

Deterministic ingestion v0 is a graph of narrow derivations, not a monolithic
processor. Each component owns one bounded transformation and records its own
contract version, processor version, complete configuration identity, input
evidence, output evidence, warnings, and stable result identity.

The graph begins with immutable raw extraction evidence. Page layout provides a
shared geometric proposal. Structure and candidate stages derive typed,
source-backed proposals. Reconstruction and composition stages combine exact
upstream artifacts. Clean transcript projectors remove only typed artifacts and
retain the evidence needed to reproduce and audit each decision.

## Planned composition root

Iteration two adds `BaseDeterministicProcessor` and its concrete
`DeterministicProcessor` implementation. `PilotDeterministicProcessor`
specializes the concrete processor and encapsulates one verified
`PdfProcessedDocument`, including its retained exact `ExtractionResult`.

The composition root is an ordering boundary, not a replacement contract. It
runs only a validated prefix of extraction verification, layout, structure,
equation detection, table detection and reconstruction, figure detection,
structured transcription, clean transcript v2, derivation audit, and audited
corpus projection. Every stage retains its existing result type, processor and
configuration identity, warnings, and failure semantics.

`PdfProcessedDocuments` is the ordered corpus container. Its documents are
processed independently; collection order is retained, but no document can use
another document's derived state or disappear because a neighboring document
fails.

## Determinism Contract

A component may claim deterministic output only when:

1. all behavior-affecting input evidence is explicit and validated;
2. processor and contract versions are recorded;
3. complete configuration participates in identity;
4. ordering and normalization rules are stable;
5. resource bounds are enforced before expensive analysis;
6. uncertainty is represented rather than silently resolved; and
7. the component performs no hidden model call, publication, or mutable-state
   lookup.

Stable identity is evidence of repeatable software derivation, not proof of
semantic, scientific, mathematical, or publication correctness.

## Composition Boundaries

Optional OCR, equation recognition, and relevance processors remain injected
boundaries with explicit backend and resource identity. Deterministic stages may
assemble requests, retain returned observations, and deterministically project
those observations. They must not claim that a stochastic backend can be
recomputed byte-for-byte.

The generic `BoundedProcessingCoordinator` is also outside the deterministic
component family: it coordinates isolated work items and preserves processor
failures and cache identity, while the injected `ProcessingProcessor` determines
the actual derivation. It is not the planned top-level
`DeterministicProcessor` and is not implicitly invoked by that name.

## Component Architecture

- [Page layout](layout/index.md) establishes conservative page-local order.
- OCR reconciliation preserves native and OCR streams separately.
- Article structure proposes headings, hierarchy, bibliography observations,
  and appendices from exact layout evidence.
- Equation, table, and figure detectors retain exact regions and context.
- Table reconstruction proposes cells, spans, headers, and continuations.
- Structured transcription composes exact typed objects and explicit omissions.
- Clean transcript projection applies conservative, typed cleanup.
- Derivation audit independently walks the supplied artifact graph and reports
  stable provenance findings.

See [implementation.md](implementation.md) for concrete classes and tests and
[the ingestion v0 architecture](../architecture.md) for the enclosing system.
