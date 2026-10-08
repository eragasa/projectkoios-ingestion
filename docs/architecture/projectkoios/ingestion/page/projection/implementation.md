# `projectkoios.ingestion.page.projection` implementation

## Status and boundary

Architecture-only clean rewrite. The prototype proves feasibility but defines no API, wire format, identity, validation report, or compatibility obligation. Planned package initializers are docstring-only ownership markers.

Page projection imports current canonical values directly from `transcript.reading.evidence` and `artifact.managed.verification`. It has no source-provider, MongoDB, disk, legacy, report-replay, or migration subpackage.

## Request and pure action

`PageProjectionRequest` binds one exact current `ReadingEvidenceDocument`, projection/inventory identities, explicit text/caption policy, and one successful `ManagedArtifactVerificationResult` whose evidence inventory exactly covers every source/media reference required by that document. Payload bytes are not retained.

`PageProjectionActionizer` performs no I/O. It:

1. verifies current contract and exact document/projection/inventory binding;
2. verifies one-to-one artifact verification coverage and identity freshness;
3. preserves canonical page order and location;
4. projects `ReadingTextEvidenceBlock` clean paragraph/heading text exactly;
5. emits each configured figure caption exactly once;
6. rejects duplicate caption identities or normalized caption/text duplication;
7. validates but emits no table/equation/media text;
8. preserves explicit limitations; and
9. derives bounded page/result identities from canonical values only.

The page projector does not repeat raw baseline/summary coverage heuristics from the prototype. Completeness and producer reconciliation are reading-evidence responsibilities. Page projection validates its immediate input contract rather than reinterpreting upstream evidence.

## Output

`PageProjectionTextBlockStyle` is closed to `PARAGRAPH`, `HEADING`, and `FIGURE_CAPTION`. Text blocks bind exact text and reading source identity. Page and inventory values preserve citation-aligned physical/printed location and complete order. Windowing groups immutable result pages without altering identity.

Search owns chunking, embeddings, ranking, and final admission. Page projection does not imply citation support, proofreading, rights, human acceptance, or scientific validity.

## Bounds and identity

`PageProjectionLimits` owns page, block, projected text, verification evidence, and aggregate/pre-hash ceilings. Identity inputs are validated, serialized once through the canonical one-way serializer, and fingerprinted through `SHA256Fingerprinter`. Prototype IDs, paths, report bytes, provider names, and database configuration never participate.
