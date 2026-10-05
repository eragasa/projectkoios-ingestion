# Extraction storage implementation

`AbstractExtractionPublicationStore.publish()` accepts one
`ExtractionPublicationRequest` and returns one `ExtractionPublicationResult`.
An extraction manifest identity is create-once: replaying the exact request is
idempotent, while attempting to publish different decomposition bytes for that
manifest is a concrete `ExtractionPublicationError`. Multiple versioned
manifests may retain different decompositions of the same source document.

The disk adapter is authoritative. It writes canonical extraction JSON into a
private content-addressed object tree and then appends a bounded checksummed
journal record. Both object and journal writes are fsynced. Journal records form
a SHA-256 chain, retain exact payload size and identity, and tolerate only a
torn terminal record; the next exclusive writer truncates that incomplete tail.
Complete malformed records fail closed.

The MongoDB adapter is a rebuildable projection. It writes separate document,
page, block, warning, and manifest collections. Large PDF/media bytes are never
stored in MongoDB. The final document manifest is written last with
`publication_state=complete`; consumers must ignore incomplete publications.
Projection writes are create-once and idempotent by stable identity and exact
publication digest.

## Provider actions

Extraction storage exposes independently typed owner operations for an external
workflow service rather than owning scheduling, queues, leases, retries, or
cross-stage batch lifecycle. Each operation uses a stable action request,
idempotency key, bounded exact evidence, compact result, actionizer identity,
and an explicit continue/retry/authority/stop disposition.

`ExistingExtractionArtifactValidationActionizer` validates one retained
`ExtractionResult` through the nominal `ExtractionArtifactReader` port. Its
request binds the opaque artifact reference and authority identity to expected
artifact, source, document, manifest, canonical payload, publication request,
and count evidence. The action recomputes all intrinsic identities at the trust
boundary. Its result retains only hashes, IDs, byte sizes, and counts; it never
retains the deserialized extraction graph. Exact replay is stable. Changed or
invalid bytes stop as invalid evidence, expected-versus-actual identity drift
stops as ambiguous evidence, and typed reader failures retain their authority
or identical-retry disposition.

`BoundedExtractionFreezeActionizer` owns one Class-C native extraction. Its
request binds opaque source/artifact references, separate read/write authority
identities, exact source bytes and locator digest, page bound, and exact
extractor/configuration/cache identities. It first reuses and validates a
canonical frozen artifact. Only when none exists does it read the source,
extract once, and create the canonical artifact. The compact result exposes a
successful artifact-validation request/result for the publication transition;
it does not retain source bytes or the extraction graph. A retry after a
successful freeze never invokes the extractor again.

`ValidatedExtractionJournalPublicationActionizer` re-reads and revalidates
one artifact already accepted by the artifact-validation action before it calls
the authoritative journal backend. The request binds the successful validation
request/result, opaque journal target, and write authority. This disk-only action
never opens MongoDB. Replaying the same request returns the same checksummed
journal record with `replayed=true`; changed bytes or target identity stop before
a new record is accepted.

`ExtractionProjectionInventoryActionizer` queries the five owned MongoDB
collections through a nominal reader port. It returns only per-collection
counts plus sorted identity and publication digests. It never retains projected
documents. `SelectedExtractionProjectionRecoveryActionizer` binds one target to
an exact authoritative journal count and head plus an ordered subset of full
publication records. The MongoDB backend rejects journal drift, changed selected
records, target-identity drift, and a nonempty target when an empty rebuild was
requested. Its result distinguishes newly projected from unchanged records and
includes the resulting compact projection inventory.

Operational scripts remain migration and equivalence fixtures. A workflow
service owns cross-action orchestration, child batches, approvals, durable
checkpoints, and retry timing while invoking these actions without changing
their requests.
