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

Operational scripts remain migration and equivalence fixtures. A workflow
service owns cross-action orchestration, child batches, approvals, durable
checkpoints, and retry timing while invoking these actions without changing
their requests.
