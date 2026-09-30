# Reference evidence projection

## Contract metadata

| Field | Value |
|---|---|
| Contract ID | `projectkoios.ingestion.reference-evidence` |
| Target version | `0.1.0` |
| Artifact schema generation | `1` |
| Status | Proposed |
| Specification revision | Git commit containing this document |
| Owner | `projectkoios-ingestion` |
| Acceptance authority | Project Koios operator after ingestion-owner and materially affected references-consumer review |
| Architecture context | [Project Koios current architecture](https://github.com/eragasa/projectkoios/blob/main/docs/architecture/README.md) and [ingestion implementation architecture](../architecture/ingestion/implementation/index.md) |
| Task | `ING-REFERENCE-EVIDENCE-01`, `projectkoios-ingestion#3` |
| Predecessor | None registered; the owner-internal canonical transcript materializer publishes this projection |
| Supersedes | None while proposed |
| Dependencies | Owner-internal extraction, canonical clean-transcript result, and derivation-audit evidence |
| Consumers | `projectkoios-references` through its adapter under `projectkoios-references#18` |
| Compatibility | New projection; compatibility is unknown until real consumer conformance is recorded |
| Effective baseline | None while proposed |

## Status and conformance boundary

This contract is **Proposed**, not accepted. The implementation and sanitized
producer fixtures are available for consumer work, but a real references
consumer and cross-repository conformance result remain pending under
`projectkoios-references#18`. The contract is not yet registered in the shared
catalog, and no end-to-end conformance claim is made.

The normative sections are **Producer input and lineage**, **Record fields and
serialization**, **Failure behavior**, and **Authority limits**. Conformance
subjects are the ingestion producer, strict parser/verifier, and the separate
references-owned consumer adapter.

This projection evaluates the single canonical clean-transcript result. Its
transcript member records the exact result identity, producer provenance,
configuration digest, text identity, status, warnings, and layout/transcription
lineage. It has no clean-transcript generation or compatibility-version field.
Unknown legacy keys fail strict parsing rather than selecting an old shape.

## Producer input and lineage

A complete record MUST be built from exactly one:

- completed extraction result and exact serialized extraction artifact;
- `AUTOMATED_UNREVIEWED` clean-transcript result;
- recorded passing derivation-audit report covering the extraction manifest,
  extracted document, every named layout, structured-transcription result, and
  clean-transcript result; and
- exact serialized clean-transcript and derivation-audit artifacts.

The producer MUST reject mismatched logical source, blob, content hash,
document, transcript, layout, or audit evidence. It MUST reject a failed audit,
a passing audit with findings, incomplete required layer coverage, and artifact
bytes that contradict the supplied immutable contracts. This validation proves
that the reported producer evidence belongs to one exact source-byte identity;
it does not independently re-run the audit.

## Record fields and serialization

The immutable record contains:

- contract ID/version/status, schema generation, media type, and producer
  generator name/version;
- explicit completeness plus typed reasons when not complete;
- source blob ID, SHA-256 algorithm/digest, exact byte length, and media type;
- exact extraction-artifact digest/length, extraction contract, manifest and
  document identities, status, extractor version, configuration identity, and
  warning count;
- exact serialized clean-transcript digest/length, result identity,
  `automated_unreviewed` status, structured-transcription and ordered-layout
  identities, consolidated-text digest/length, projector provenance,
  configuration digest, and warning count;
- exact derivation-audit artifact digest/length, contract/report/status and
  validator versions, complete audited artifact identities and layer counts,
  finding count, the scope `recorded_producer_derivation_audit`, and
  `independently_revalidated: false`; and
- explicit authority limitations.

No source filename, private path, source locator, workspace filename, machine
locator, protected text, clean text, quotation, credential, or access-control
detail is serialized.

Serialization is UTF-8 canonical JSON with lexicographically sorted object keys,
no insignificant whitespace or trailing newline, JSON string escaping as
implemented by the bounded serializer, and a maximum of 262,144 bytes. The
record ID is `reference-evidence-record:sha256:<digest>` over every record field
except the ID itself. Identical inputs replay byte-identically. Any changed
bound evidence changes the record identity.

## Failure behavior

The public parser MUST reject:

- malformed UTF-8/JSON, duplicate fields, unknown fields, excessive nesting,
  or oversized input;
- noncanonical serialization or inconsistent content identity;
- unknown contract, schema, generator, transcript-generation, or dependent
  contract versions;
- incomplete or unsupported records presented for reuse;
- contradictory extraction, transcript, audit, status, or lineage fields; and
- absent required audit coverage.

The verifier requires the consumer-known source SHA-256, byte length, and media
type and rejects stale or different-source evidence. When exact producer
artifact bytes are supplied, it also verifies their digest and length. Hash
verification of recorded artifacts is not independent derivation revalidation.

## Authority limits

A complete record means only that ingestion recorded internally consistent,
source-bound processing evidence under the named versions and that the recorded
derivation audit passed. `AUTOMATED_UNREVIEWED` is preserved exactly.

The record MUST NOT imply:

- human proofreading or editorial acceptance;
- extraction or semantic accuracy;
- mathematical or scientific correctness;
- independent audit revalidation;
- producer authentication from content addressing alone;
- canonical-reference promotion or asset attachment;
- claim support, manuscript use, rights clearance; or
- publication suitability or permission.

`projectkoios-ingestion` owns this producer record. `projectkoios-references`
owns its consumer adapter and any asset-to-processing linkage observation. A
consumer MUST receive record bytes through an injected boundary; it MUST NOT
construct ingestion workspace paths or infer evidence from producer filenames.

## Fixtures and pending acceptance evidence

Sanitized deterministic fixtures are under
`tests/fixtures/reference_evidence/`. `complete.json` is a valid producer-shaped
record with synthetic identities. Parser tests inject removed transcript keys
and require strict unknown-field rejection. The fixture contains no private
evidence.

Before acceptance, the remaining evidence includes a real references adapter,
fixture exchange against these exact bytes, a recorded cross-repository
conformance result, materially affected consumer review, catalog registration,
and a separate human lifecycle decision. Passing ingestion tests alone does not
satisfy those requirements.
