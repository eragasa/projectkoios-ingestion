# `projectkoios.ingestion.transcript.reading.evidence` implementation

## Status and clean-break boundary

Architecture-only rewrite. Prototype code remains executable discovery material until replaced, but it is not authoritative for API, wire format, identity, or persistence. Every new package initializer is a docstring-only marker; defining leaves are imported directly.

## Exact producer input

`ReadingEvidenceProjectionRequest` binds:

- one `ReadingDocumentProducerEvidence`;
- complete `ReadingPageTextProducerEvidenceInventory` with separate native/OCR streams and explicit selection;
- complete `ReadingStructuredItemProducerEvidenceInventory` owning semantic item kind and order;
- complete `ReadingCleanTextProducerEvidenceInventory` owning cleaned source-block text and transformations;
- complete figure, table, and equation producer inventories;
- exact managed artifact references;
- one expected inventory; and
- immutable `ReadingEvidenceProjectionConfiguration` and limits.

The request contains no canonical output pages. Producer document/source/page identities must agree before any join or identity derivation.

## Deterministic projection

`ReadingEvidenceProjectionActionizer` is the sole normal constructor of complete `ReadingEvidenceDocument` values. It performs no I/O.

For text items:

1. accept only configured structured item kinds `PROSE` and `HEADING`;
2. resolve every structured source-block identity to exactly one `ReadingCleanTextProducerEvidence` on the same page and selected page stream;
3. require resolved records to be contiguous in clean-text producer order and unused by another emitted text item;
4. derive output text as the exact clean texts joined with one `"\n"` separator in producer order;
5. assign paragraph/heading role and page order from the structured item; and
6. bind `ReadingTextBlockProjectionBasis.CLEAN_PRODUCER_EXACT`, structured item identity, clean-text record identities, raw/clean digests, and transformation evidence into block identity.

For visual/equation items, the projector joins structured source-object identity and page/order to exactly one eligible producer record. Figure captions are selected only from explicit `CAPTION` associations under the configured deterministic rule. Table evidence remains structured evidence, not invented text. Only configured primary equation evidence enters ordered blocks; auxiliary/rejected evidence remains retained outside the ordered block inventory. Equation text never enters page text merely because recognition succeeded.

Unmatched required structured items, multiply matched producer records, page disagreement, duplicate source use, missing references, inconsistent review gates, or out-of-bound work fail projection. No adapter or MongoDB provider infers missing semantics.

## Canonical values

- `ReadingTextStreamKind`: `NATIVE` and `OCR`.
- `ReadingTextSelectionBasis`: `NATIVE_EXACT` and `OCR_COMPOSITION_EXACT`.
- `ReadingTextBlockProjectionBasis`: `CLEAN_PRODUCER_EXACT`.
- `ReadingAssociationRole`: `CAPTION`, `LEGEND`, `NOTE`, `SUBFIGURE_LABEL`, `TITLE`.
- `ReadingVisualEvidenceStatus`: `PROPOSED`, `AMBIGUOUS`, `OBSERVED`.
- `ReadingReviewStatus`: `UNREVIEWED`, `ACCEPTED`, `REJECTED`.
- `ReadingTableBoundaryKind`: `RULED`, `UNRULED`, `MIXED`.
- `ReadingEquationRecognitionStatus`: `NOT_REQUESTED`, `DEFERRED`, `SUCCEEDED`, `FAILED`.
- `ReadingEquationSelectionDisposition`: `PRIMARY`, `AUXILIARY`, `REJECTED`.

Role-specific fields use role-specific semantic inventories or typed identity values; the generic identity inventory cannot substitute for grammar validation.

`ReadingEvidencePage` binds page location, streams, selection, and ordered blocks. `ReadingEvidenceDocument` binds source identity, complete page inventory, retained auxiliary evidence, managed references, exact producer lineage, and limitations. `ReadingEvidenceInventory` is recomputed observationally. `ReadingEvidenceReconciliation` compares it with `ExpectedReadingEvidenceInventory`; expected values cannot self-certify completion.

## Identity

All external values and aggregate work are bounded and semantically validated before hashing. Each typed identity material is serialized once through the canonical one-way serializer and those exact bytes are fingerprinted by `SHA256Fingerprinter`. Prototype paths, IDs, JSON bytes, database names, and provider configuration do not participate.

## Source and persistence

`ReadingEvidenceSourceActionizer` returns only current canonical records. The normal provider is MongoDB, materialized from pure projection results and rebuildable authoritative inputs. Large payload bytes remain outside MongoDB as managed references.

MongoDB schema evolution is handled only by the explicit side-by-side versioned migration hierarchy. Core readers never decode old schemas.

## Exclusions

The package does not own model execution, retries, leases, checkpoints, concurrency, approvals, database migration orchestration, Search chunks, embeddings, ranking, rights, publication, or scientific acceptance.
