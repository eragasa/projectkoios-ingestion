# Page-projection publication

## Ownership and scope

Ingestion owns one durable publication command for one exact managed PDF. A
nine-document operation is nine independent commands. The command verifies the
managed bytes, extracts native PDF text, constructs current reading source and
document evidence, derives PageProjection A and evidence-enrichment B, and
commits private content-addressed evidence plus a transport-safe receipt.

The action does not import or name References, Courses, Search, HTTP, or a web
framework. A PDF reused by another course with the same Ingestion pipeline
produces the same source, document, A, B, payload, receipt, and publication
identities. External queue, selection, asset-observation, runtime-evidence,
source-asset, decision, and binding identities belong to API composition and
are absent from Ingestion identities.

The pure `PageProjectionActionizer` is unchanged. Publication is a distinct
effect boundary with journal, compare-and-swap, and replay semantics.

## Owner command

Core imports:

- `projectkoios.ingestion.page.projection.publication.request.PageProjectionPublicationRequest`
- `projectkoios.ingestion.page.projection.publication.actionizer.PageProjectionPublicationActionizer`
- `projectkoios.ingestion.page.projection.publication.result.PageProjectionPublicationResult`
- `projectkoios.ingestion.page.projection.publication.error.PageProjectionPublicationError`
- `projectkoios.ingestion.page.projection.publication.error.PageProjectionPublicationFailureReason`
- `projectkoios.ingestion.page.projection.publication.codec.PageProjectionPublicationReceiptCodec`

The cohesive receipt codec owns canonical JSON encoding and exact validated
decoding. It uses the repository `CanonicalJsonSerializer` and bounded
`JsonParser`; it is not another action or compatibility boundary.

Trusted disk composition:

- `projectkoios.ingestion.integrations.disk.page.projection.publication.runtime.DiskPageProjectionPublicationRuntime`
- `projectkoios.ingestion.integrations.disk.page.projection.publication.store.DiskPageProjectionPublicationStore`

Package initializers contain only ownership docstrings and export no names.

## Request field audit

| Field | Trust and meaning | Identity role |
| --- | --- | --- |
| `source_artifact` | Exact locator-free SHA-256, byte length, and managed media type | Source subject and semantic publication input |
| `expected_pipeline_configuration_id` | Caller echo of the trusted actionizer freshness identity | Exact request fingerprint; checked before CAS/source read on a non-replay |
| `maximum_page_count` | Caller narrowing bound; cannot exceed the trusted ceiling | Exact request fingerprint, not A/B identity |
| `maximum_block_count` | Caller narrowing bound; cannot exceed the trusted ceiling | Exact request fingerprint, not A/B identity |
| `idempotency_token` | Opaque bounded caller token | Selects an entry only inside the owner-derived scope; not publication/A/B identity |
| `expected_current_publication_id` | `None` means require no current head; otherwise exact CAS head | Exact request fingerprint; not publication/A/B identity |

The request has no path, bytes, title, citekey, free idempotency scope, external
authority join, or caller-controlled provider/profile/version ceiling.

Trusted runtime owns the source root and exact artifact-to-relative-path
bindings, publication root, deployment scope, owner authority, profile,
provider, dependency versions, stream limit, absolute source/page/block/payload
ceilings, and extraction configuration. Browser bounds can only narrow these
ceilings.

`request_fingerprint` hashes every request field except the token. `request_id`
hashes that fingerprint plus the token. The publication identity excludes the
token, CAS expectation, store scope, source path, and external correlation.

## Replay and CAS order

Under one source-subject journal lock:

1. Derive the idempotency scope from the trusted store scope plus managed
   artifact identity.
2. Look up the digest of the opaque token.
3. If its stored request ID and fingerprint match, reread and verify the exact
   committed receipt and private payload and return `REPLAYED_IDENTICAL`.
4. If the token exists for another request, stop with
   `IDEMPOTENCY_CONFLICT`.
5. Only when the token is absent, validate trusted pipeline/profile/ceilings.
6. Compare the authoritative subject head with
   `expected_current_publication_id`; stop on mismatch.
7. Verify and reread exact source bytes, derive current evidence, and prepare
   content objects.
8. Create-or-verify payload and receipt objects.
9. Atomically replace and sync one complete subject state containing the head
   and idempotency entry.
10. Reread state, receipt, and payload, verify hashes and lengths, and return
    `CREATED`.

Exact replay therefore precedes pipeline freshness, head freshness, source
availability, and source reads. A missing token never bypasses CAS.

## Durable completion

Private payload and safe receipt objects are immutable and content addressed.
The atomically replaced subject-state file is the authority point. Objects
written before that point are harmless unreferenced objects. Interruption before
the state replacement leaves the command unapplied; identical retry safely
reuses equivalent objects. Interruption after replacement replays from the
committed state. Receipt and payload identity collisions fail closed before any
new subject-state authority is committed.

The committed private payload contains the complete current nested B → A →
source/document graph and managed verification evidence. It excludes transient
PDF bytes and extraction timestamps. The source PDF is never modified.

## Result and receipt

The action result contains only these HTTP-safe scalar fields:

- `disposition`: `CREATED` or `REPLAYED_IDENTICAL`;
- `idempotency_scope_id`;
- `request_id`;
- `receipt_id`, `receipt_sha256`, and `receipt_byte_length`;
- exact immutable `receipt_body_json`;
- `committed_publication_id`; and
- derived `result_id`.

The receipt body is byte-for-byte identical on creation and replay. Operation
disposition is outside that receipt so replay can report its disposition
without rewriting authority evidence. The receipt includes safe identities and
counts for the managed artifact, verification, extraction manifest/document,
current reading source/document/projection/inventory/source result, A, B,
private payload, pages, blocks, warnings, and limitations. It contains no text,
private path, filename, locator, source bytes, credentials, or external
References/Courses join.

No separate preview or status action is required. Request construction is
pure, exact replay is read-only, non-replay mutation is guarded by explicit
CAS, and success is returned only after a post-commit owner reread.

## Closed failures

`PageProjectionPublicationError.reason` is one
`PageProjectionPublicationFailureReason`:

- `INVALID_REQUEST`
- `UNSUPPORTED_MEDIA`
- `UNSUPPORTED_PROFILE`
- `IDEMPOTENCY_CONFLICT`
- `STALE_CURRENT_PUBLICATION`
- `SOURCE_BINDING_UNAVAILABLE`
- `SOURCE_UNAVAILABLE`
- `SOURCE_BYTES_DIFFER`
- `DEPENDENCY_UNAVAILABLE`
- `DEPENDENCY_VERSION_DIFFERS`
- `RESOURCE_LIMIT_EXCEEDED`
- `PROJECTION_VALIDATION_FAILED`
- `PUBLICATION_COLLISION`
- `PUBLICATION_INTEGRITY_INVALID`
- `PUBLICATION_STORE_UNAVAILABLE`
- `UNEXPECTED`

Messages are bounded and sanitized; callers map the enum and never parse the
message. No failure result is a success result.
