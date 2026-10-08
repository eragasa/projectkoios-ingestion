# Reading-evidence storage implementation

## Ownership

This hierarchy owns the backend-neutral persistence contract for one current canonical `ReadingEvidenceDocument`. It owns logical collections, current schema identity, bounded canonical JSON records, completion-manifest semantics, pure read-model projection, strict typed reconstruction, materialization/source ports, and independent equivalence inputs.

It contains no MongoDB, SQLite, filesystem, BSON, SQL, path, cursor, credential, retry, cutover, or migration-orchestration type.

## Pure read-model projection

`ReadingEvidenceStorageProjector` accepts one complete reconciled `ReadingEvidenceProjectionResult` and `ReadingEvidenceStorageProjectionConfiguration`. It performs no I/O and emits one immutable `ReadingEvidenceReadModel` containing canonical `ReadingEvidenceStorageDocument` members for these logical collections:

- document header;
- pages;
- ordered blocks;
- clean-text, figure, table, and equation producers;
- managed-artifact references;
- limitations; and
- one completion manifest.

The document header does not contain unbounded child arrays. Membership is defined by generation/document scope plus exact manifest collection counts and digests. Blocks reference producer records by stable semantic identity. Large artifact bytes are never included.

Every member contains stable logical identity, current schema identity, generation identity, canonical evidence-document identity, semantic record kind, canonical JSON, a projected-content digest, and a full canonical digest. Derived canonical identities are stored as evidence but are never constructor inputs during reconstruction.

The completion manifest is projected only after all child members exist logically. It binds the original reading projection-result identity, evidence-document identity, independently observed inventory identity, and exact per-collection count/digest evidence. Physical adapters must materialize it last.

## Reversible current-schema boundary

`ReadingEvidenceStorageJsonContract` is the sole reversible typed JSON boundary for persisted reading evidence. It has an explicit registry of admitted current canonical values and enums. It rejects unknown types, fields, enum members, duplicate JSON fields, malformed UTF-8, non-RFC constants, non-finite numbers, out-of-bound documents, and mismatched stored derived identities.

`ReadingEvidenceReadModelVerifier` accepts a complete bounded read model, verifies the completion manifest and every member digest, reconstructs canonical values through public constructors, independently observes `ReadingEvidenceInventory`, and compares document, inventory, and projection identities. It does not query a backend.

Core reconstruction decodes only the current schema and contains no legacy or provider branch.

## Equivalence

`ReadingEvidenceEquivalenceVerifier` remains separate from reconstruction. It compares two already-verified source results for exact canonical document, independently observed inventory, and projection-result equivalence. Same-store replay additionally requires matching baseline/replay materialization scope and replay evidence with zero created members. The result is a technical finding and grants no migration or cutover authorization.

## Adapter ports

`ReadingEvidenceMaterializer` is the effectful write port. A concrete adapter receives one already-projected read model, exact target, physical mapping, and authority; it creates or exactly replays immutable members and materializes the completion manifest last.

`ReadingEvidenceReadModelReader` is the effectful read port. A concrete adapter requires a completion manifest, performs bounded exact reads for one generation/document, and returns backend-neutral storage documents. The neutral verifier—not the adapter—owns typed reconstruction and equivalence.

MongoDB is the normal operational adapter. Disk and SQLite can implement the same ports. The authoritative disk journal and object storage remain outside this rebuildable read-model contract.

## Workflow boundary

Workflow owns iteration, retries, leases, checkpoints, orphan cleanup, migration sequencing, write-freeze barriers, cutover, rollback, and destructive cleanup. No storage value infers those lifecycle states.
