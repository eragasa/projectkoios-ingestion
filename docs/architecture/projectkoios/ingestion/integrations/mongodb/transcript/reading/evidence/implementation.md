# MongoDB reading-evidence implementation

## Ownership

This integration is a thin MongoDB front end for the backend-neutral reading-evidence storage contract owned by `projectkoios.ingestion.storage.transcript.reading.evidence`.

It owns only:

- physical MongoDB collection mapping and BSON byte bounds;
- validation that an injected database capability matches the requested target;
- create-once exact-replay writes of already-projected storage documents;
- completion-member-last write ordering;
- bounded queries for one exact completed generation;
- translation of MongoDB failures into typed provider errors; and
- provider-specific scope-index readiness.

It does not own canonical record decomposition, reversible reading-evidence JSON, logical schema semantics, completion-manifest meaning, canonical reconstruction, or equivalence. Those are backend-neutral and reusable by disk, SQLite, and MongoDB adapters.

## Index readiness

`MongoReadingEvidenceIndexReadinessActionizer` separately creates or exactly verifies one deterministic scope index for every configured physical collection. The source reader requires those definitions before issuing document queries. Index mutation is not hidden inside materialization or reading.

## Current-schema materialization

`MongoReadingEvidenceMaterializer` accepts a complete `ReadingEvidenceReadModel` produced by `ReadingEvidenceStorageProjector`, an exact target, physical MongoDB configuration, and authority identity. It does not inspect or reinterpret semantic payloads.

It validates every projected JSON object and BSON size, writes non-completion members using create-once exact replay, and writes the already-projected completion member last. Existing `_id` with different complete content fails closed. Partial generations lack a completion member and are invisible to the normal source. Workflow owns retry and orphan cleanup.

## Current-schema source

`MongoReadingEvidenceReadModelReader` first requires exactly one current-schema completion member, then performs bounded exact generation/document reads using manifest counts. It returns only `ReadingEvidenceStorageDocument` values assembled into `ReadingEvidenceReadModel`.

`MongoReadingEvidenceSourceActionizer` composes that reader with backend-neutral `ReadingEvidenceReadModelVerifier`, returning `ReadingEvidenceSourceResult`. The Mongo layer never constructs canonical domain values itself and never decodes old schemas.

## Migration boundary

The current MongoDB reading-evidence package implements no migration owner, migration request, inventory observer, cutover, rollback, or cleanup operation. Any future side-by-side schema migration remains an external, separately designed and authorized Workflow composition using backend-neutral reconstruction and equivalence evidence. No live database operation is part of the current implementation validation.
