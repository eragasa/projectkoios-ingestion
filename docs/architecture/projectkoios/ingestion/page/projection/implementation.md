# `projectkoios.ingestion.page.projection` implementation

## Status and boundary

Implemented pure current-schema projection. Package initializers are docstring-only ownership markers, and no flat-module API or alternate projection path exists.

Page projection imports current canonical values directly from `transcript.reading.evidence` and `artifact.managed.verification`. It has no source-provider, MongoDB, disk, report-replay, migration, Search, Agent, or Workflow dependency.

## Request and pure action

`PageProjectionRequest` directly specializes `projectkoios.base.DataObjectActionRequest`. It binds:

- one exact current `ReadingEvidenceSourceResult`, which already binds its document, projection result, observed inventory, and provider verification;
- one successful `ManagedArtifactVerificationResult`; and
- one required identity-bearing `include_figure_captions` boolean.

Paragraph and heading projection is mandatory and complete. When `include_figure_captions` is `True`, every non-`None` canonical figure caption is emitted exactly once. When it is `False`, no caption text is emitted. There are no paragraph/heading policy switches or free-form modes.

The request reconstructs every page-projection-relevant location, structured order, text block, figure caption, visual block, block inventory, page, and page inventory. It then reconstructs the reading source request/result, independently recomputes the current reading inventory, requires exact document artifact-reference coverage, reconstructs managed-artifact request/evidence/result values to reject stale identities, and applies count/byte/work ceilings. The actionizer and result each reconstruct the complete request before deriving output, so post-construction changes fail closed. The request identity contains the exact source-result identity, artifact-verification-result identity, caption-policy boolean, and contract version; callers cannot supply duplicate document/projection/inventory bindings.

`PageProjectionActionizer` directly specializes `projectkoios.base.DataObjectActionizer` and performs no I/O. It:

1. preserves every canonical page, physical index, printed label, page identity, and reading order;
2. projects `ReadingTextEvidenceBlock` paragraph/heading text exactly;
3. optionally emits configured figure captions at their canonical figure order;
4. rejects duplicate admitted caption identities;
5. rejects NFC whitespace-compacted caption collisions with emitted text or another admitted caption;
6. validates but emits no figure media, table text, equation text, recognition proposal, or payload byte;
7. retains upstream `ReadingEvidenceLimitationInventory` without relabeling it; and
8. adds the complete fixed page-projection non-authority limitation inventory.

The page projector does not repeat raw baseline/summary coverage heuristics. Completeness and producer reconciliation remain reading-evidence responsibilities.

## Output

`PageProjectionTextBlockStyle` is closed to `PARAGRAPH`, `HEADING`, and `FIGURE_CAPTION`. Paragraph and heading blocks bind their canonical reading block identity. Caption blocks bind their canonical caption identity. Block order retains the upstream index, including gaps caused by intentionally excluded visual/table/equation blocks.

`PageProjectionPage` preserves the canonical reading-page identity and exact `ReadingPageLocation`. `PageProjectionPageInventory` preserves contiguous physical order and exact page identities. `PageProjectionPageWindowInventory` groups immutable pages without changing page, block, source, or projection identities.

`PageProjectionResult` directly specializes `projectkoios.base.DataObjectActionResult`. Construction reruns the pure page derivation and rejects forged pages, incomplete coverage, altered limitations, or unsupported processor identity/version. Its semantic properties expose the exact source, document, upstream projection, upstream inventory, and artifact-verification identities.

Search owns chunking, embeddings, ranking, evidence-bundle construction, and final retrieval admission. The pure typed call is this slice's complete executable boundary; there is no Ingestion workflow script, CLI, batch runner, pipeline wrapper, or source-to-verification convenience action. A future durable composition belongs to Applications and Workflow only when separately authorized. Page projection does not imply claim support, citation acceptance, proofreading, rights, publication suitability, or scientific validity.

## Bounds and identity

`PageProjectionLimits` owns page, block, per-page block, projected text, verification evidence, observed artifact byte, aggregate work, processor-version, identity, and pre-hash ceilings.

Identity material is validated, serialized once through `CanonicalJsonSerializer`, checked against the page-projection pre-hash ceiling, and fingerprinted through `SHA256Fingerprinter`. Hierarchical block, block-inventory, page, page-inventory, limitation, window, request, and result identities avoid hashing an unbounded document payload at once. No independent provider or database configuration fields, paths, payload bytes, or validation reports are accepted. Request and result identities transitively bind the exact upstream source and managed-artifact verification attestations, including their provider and verifier provenance; block, block-inventory, page, and page-inventory identities remain provider-neutral.
