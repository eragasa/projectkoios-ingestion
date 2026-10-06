# Extraction storage implementation

The reviewed module-to-package inventory for this owner is maintained in the
[storage structural path map](structural-path-map.md). Package initializers are
ownership markers; callers import the defining leaf directly.

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
projected-content digest.

## Pure extraction projection

The extraction read path uses the Projector terminology literally:

| Term | Concrete owner | Meaning |
| --- | --- | --- |
| source evidence | `ExtractionPublicationEvidence` | One validated journal record plus its exact immutable payload bytes |
| configuration | `ExtractionProjectionConfiguration` | Complete schema, identity-namespace, version, and completion-state choices |
| projector | `ExtractionProjectionProjector` | Pure parsing and transformation only |
| projection value | `ExtractionReadModel` | Canonical backend-neutral documents for five logical collections |
| projection member | `ExtractionProjectionDocument` | One immutable canonical JSON document with full content evidence |
| materializer | `MongoExtractionProjectionMaterializer` | Effectful create-once writes to physical MongoDB collections |
| pipeline | `ExtractionProjectionMaterializationPipeline` | Workflow prototask joining two synchronous actionizers: Projector, then Materializer |
| materialization target | `ExtractionProjectionTargetIdentity` | Explicit deployment, environment, database, schema, and projection slot |
| index readiness | `ExtractionProjectionIndexReadinessActionizer` | Effectful preparation and exact observation of required physical indexes |
| projector inventory | `ExtractionProjectorInventory` | Read-only full-content observation of materialized target state |
| inventory reader | `ExtractionProjectionInventoryReader` | Adapter port used by the projector inventory |
| expected inventory | `ExpectedExtractionProjectionInventory` | Compact full-content evidence derived from immutable read models or a pre-replay snapshot |
| equivalence verifier | `ExtractionProjectionInventoryEquivalenceVerifier` | Pure comparison of expected and independently observed inventory evidence |

`ExtractionProjectionProjector` accepts no journal, database, authority, clock,
retry policy, or mutable lookup. The source evidence verifies payload byte count
and SHA-256 against its journal record before projection. The projector requires
canonical extraction-result JSON, checks document and manifest identities
against the record, derives vendor-neutral page/block/warning identities, and
rejects duplicate logical collection identities. Its read model is sorted by
logical collection and stable `_id`, so replay produces the same serialized
bytes, member digests, aggregate digest, projection identity, and result
identity.

Each projected document carries two distinct digests:

1. `projection_content_sha256` binds every projected field before the digest
   marker is inserted and is used for create-once materialization; and
2. `canonical_sha256` on `ExtractionProjectionDocument` binds the complete final
   JSON document, including that marker.

The extraction pipeline passes exact publication evidence through the pure
projector and then passes the resulting read model, explicit target, physical
configuration, and authority to the materializer. It is a workflow prototask
that owns exactly those two synchronous calls: no retries, queues, checkpoints,
or cross-record lifecycle.

The MongoDB materializer decodes only projector-produced canonical JSON. It
writes blocks, pages, warnings, and manifests before root completion documents.
Its upsert filter binds `_id` and `projection_content_sha256`, so an exact replay
replaces the exact identity while changed projected content reaches a unique-key
conflict rather than silently overwriting prior content. Index creation remains
separate adapter readiness work; it is not projection or materialization. The
index-readiness request binds the exact target, complete ordered index
configuration, and write authority. Its authority-neutral idempotency key binds
the target and configuration, while its evidence records every observed name,
ordered key, uniqueness property, and definition identity.

Failure terms are also distinct. `ProjectionPayloadError` means source bytes are
malformed, noncanonical, incomplete, or structurally invalid.
`ProjectionIdentityError` means otherwise structured record, payload, or output
identities disagree or duplicate. `ProjectionContractError` is reserved for the
fixed framework's declared source/configuration/output contract violations.
`MongoExtractionProjectionMaterializationError` begins only after successful
projection and reports BSON, size, identity-conflict, or database-write failures.

The projector inventory reads every complete stored document, serializes it as
canonical JSON, and hashes sorted `(stable identity, canonical content digest)`
pairs for each configured collection. Any stored-field change therefore changes
the collection and aggregate inventory identities. Inventory remains an
observation; a separate equivalence verifier must compare expected and observed
evidence before equivalence can be claimed. Independent-rebuild requests bind
journal-derived expected evidence to one observed target. Same-store replay
requests additionally require materialization evidence proving zero creations
and an unchanged count equal to the complete expected document count.

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

`ExtractionProjectionIndexReadinessActionizer` is one atomic owner operation.
It creates missing configured indexes, re-reads their definitions, rejects
conflicting definitions, and returns exact compact evidence without retaining
MongoDB handles or documents. Its typed request/result, stable actionizer
identity, authority, idempotency, evidence, and disposition can be represented
as Workflow token colors and transition ports. Ingestion does not infer CPN
places, guards, lifecycle, retry, concurrency, or acceptance from these types.

`ExtractionProjectionInventoryActionizer` queries the five owned MongoDB
collections through the constrained `Inventory` / `ProjectorInventory` pattern.
Its request binds an explicit target, full observation configuration, and query
authority. It returns only per-collection counts and full-content digests; it
never retains projected documents. `ExtractionProjectionSubsetRecoveryActionizer`
binds one target to an exact authoritative journal count and head plus an ordered
subset of full publication records. The MongoDB backend rejects journal drift,
changed subset records, target-identity drift, and a nonempty target when an
empty rebuild was requested. Its result distinguishes newly projected from
unchanged records and includes the resulting compact projection inventory.

Operational scripts remain migration and equivalence fixtures. A workflow
service owns cross-action orchestration, child batches, approvals, durable
checkpoints, and retry timing while invoking these actions without changing
their requests.
