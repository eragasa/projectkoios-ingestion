# `projectkoios.ingestion.reference.evidence` implementation

## Purpose

Before this slice, `reference_evidence.py` combined seven immutable records,
three status enums, validation, hard limits, construction, verification, strict
JSON parsing, typed reconstruction, and canonical serialization in one
1,259-line root module. This slice separates those roles under semantic
reference-evidence ownership and replaces duplicated JSON mechanics with the
shared `projectkoios.ingestion.json` boundary.

The target source layout is:

```text
reference/
  __init__.py
  evidence/
    __init__.py
    artifact.py
    definition.py
    status.py
    completeness.py
    limitation.py
    identity.py
    layout.py
    lineage.py
    layer.py
    source.py
    extraction.py
    transcript.py
    audit.py
    record.py
    projection/
      __init__.py
      request.py
      artifact.py
      lineage.py
      actionizer.py
    verification/
      __init__.py
      request.py
      artifact.py
      result.py
      actionizer.py
    json/
      __init__.py
      contract.py
      record.py
      artifact.py
      source.py
      extraction.py
      transcript.py
      audit.py
      layer.py
      value.py
    validation.py
    error.py
    limits/
      __init__.py
      definition.py
      error.py
```

The exact responsibility map is in
[`structural-path-map.md`](structural-path-map.md). Each planned leaf has an
individual ownership document linked from [`index.md`](index.md).

## Record ownership

The immutable records retain their wire field order, enum values, validation
meaning, and historical stable-ID material. They remain frozen dataclasses.
Raw tuple fields are replaced by immutable semantic inventories, while JSON
codecs project those inventories to the unchanged ordered arrays.

`record.py` owns only aggregate invariants and reusable-evidence policy.
`definition.py`, `status.py`, `completeness.py`, `limitation.py`, `identity.py`,
and `lineage.py` own fixed metadata, statuses, semantic collections, bounded
identity derivation, and cross-record lineage respectively. JSON output-size
enforcement belongs to the JSON package; record-level item and text ceilings
remain domain invariants.

`artifact.py` owns exact byte binding. `source.py`, `extraction.py`,
`transcript.py`, and `audit.py` own their respective evidence records.
`layout.py`, `layer.py`, and `lineage.py` own their ordered collections. Audit
scope remains explicitly `recorded_producer_derivation_audit`, and
`independently_revalidated` remains required to be false.

## Projection and verification actions

Projection is one typed synchronous action:

```text
ReferenceEvidenceProjectionRequest
  → ReferenceEvidenceProjectionActionizer.action(request=...)
  → ReferenceEvidenceRecord
```

The immutable request carries one completed extraction, one
`automated_unreviewed` clean transcript, one recorded passing derivation audit,
and their three exact serialized artifacts. It validates input types and byte
bounds before action. The stateless actionizer validates canonical producer
bytes, lineage, status, and audit consistency and returns the aggregate record,
which is also the immutable `AbstractDataObjectActionResult`. It does not re-run
extraction or audit and grants no acceptance or publication authority.

Verification is a separate typed synchronous action:

```text
ReferenceEvidenceVerificationRequest
  → ReferenceEvidenceVerificationActionizer.action(request=...)
  → ReferenceEvidenceVerificationResult
```

Its immutable request carries one evidence record, consumer-known source hash,
byte length, media type, and optional exact producer artifact bytes. The
stateless actionizer requires reusable evidence, verifies source identity, and
checks every supplied artifact. The immutable result contains the verified
record and a typed ordered tuple naming which optional artifact classes were
verified. Source verification is mandatory and therefore is not represented as
an optional flag. Verification does not infer paths or independently validate
semantic accuracy.

There are no multi-argument operation functions, forwarding methods, hidden
configuration, or lifecycle fields. Workflow remains free to expose each
actionizer as one prototask and owns orchestration outside these synchronous
actions.

## Reversible JSON boundary

`json/contract.py` owns `ReferenceEvidenceJsonContract`, specializing
`JsonContract[ReferenceEvidenceRecord]`. It composes strict bounded UTF-8
parsing, canonical compact sorted serialization, canonical replay, and domain
error translation. `json/record.py` owns the aggregate wire object;
`json/artifact.py`, `json/source.py`, `json/extraction.py`,
`json/transcript.py`, and `json/audit.py` each own one nested wire object;
`json/value.py` owns strict shared field access. No JSON leaf exceeds its
semantic role merely to keep the boundary in one file.

The package composes `JsonParser` and `JsonSerializer`; it does not call
`json.loads()` or `json.dumps()` directly. Domain errors remain domain-owned:
shared JSON parse, serialization, and limit failures are translated to
`ReferenceEvidenceParseError`, `ReferenceEvidenceError`, or
`ReferenceEvidenceLimitError` at this boundary. Structural reconstruction
failures remain wrapped as invalid reference evidence. Existing tested error
categories and useful message fragments are retained.

The wire profile remains exactly:

- UTF-8;
- lexicographically sorted object keys;
- compact separators;
- no insignificant whitespace;
- no terminal newline;
- non-finite numbers rejected; and
- maximum 262,144 bytes.

The concrete JSON limits additionally declare maximum depth, parsed/projected
item count, individual string bytes, aggregate string bytes, and numeric token
characters. These explicit parser ceilings harden resource use without changing
valid version-1 bytes.

## Compatibility and clean break

The Proposed `projectkoios.ingestion.reference-evidence@0.1.0` wire shape is
retained byte-for-byte. The Python API is unstable and receives a clean path
break:

- `projectkoios.ingestion.reference_evidence` is deleted;
- reference-evidence names are removed from `projectkoios.ingestion`;
- no compatibility module, alias, decoder, or package re-export is added; and
- every consumer imports the defining leaf.

Stored bytes remain valid because the JSON wire document contains no Python
module path. The existing canonical fixture is the pre-migration baseline:

- byte length: `3639`;
- SHA-256: `c1f2926912d8e6d5ab80e91418b8cf7ad7bf7b63ef813f8bb1e8ba63d71fa228`;
- record ID: `reference-evidence-record:sha256:225aad8e7e74ecdac07334c8cea431a7baf014e74722fe9c5f124ba9bce5c10a`.

Implementation acceptance requires identical fixture bytes, identical record
ID, parse/reconstruct/reserialize equality, and representative generated
artifact replay.

## Tests and enforcement

The broad root test moves under
`tests/projectkoios/ingestion/reference/evidence/`. A frozen fixture object owns
shared synthetic identities and records. Tests are split by record invariants,
projection, JSON, and verification concerns. Locator and claim-candidate tests
remain with their current primary owners and update imports only.

The reference/evidence source scope is added to hierarchy-smell enforcement.
The old root module and root exports are rejected by clean-wheel checks. New
package initializers are docstring-only, paths contain no flattened semantic
names or redundant `x/x.py`, immutable records are frozen, and cross-module
private imports are prohibited.

## Semantic record and projection ownership

The aggregate record does not own construction or an untyped identity helper.
`definition.py` owns stable contract metadata, `status.py` owns closed statuses,
`completeness.py` owns typed completeness reasons, `limitation.py` owns typed
limitations, and `identity.py` validates the complete historical identity input
before hashing. Ordered layout, audit-artifact, layer-count, and verified-artifact
collections are immutable semantic inventories; JSON codecs project them back to
the unchanged ordered arrays.

Projection remains the only complete-record construction operation. Its
actionizer composes state-bound artifact and lineage verifiers from
`projection/artifact.py` and `projection/lineage.py`; `ReferenceEvidenceRecord`
has no `create()` or generic `identity_for(**values)` bypass. The aggregate leaf
owns only record invariants, reusable-evidence policy, and exact lineage use.

The nested audit layer-count wire object is owned by `json/layer.py`. Aggregate
JSON codecs compose that owner and preserve the established field order and
canonical bytes.

## Migration sequence

1. Review this architecture and exact path map before source changes.
2. Capture the existing fixture digest, record ID, focused-test result, and a generated-record replay baseline.
3. Add docstring-only package markers, limits, validation, errors, and immutable record leaves.
4. Add typed projection and verification request/actionizer/result leaves without changing authority or evidence meaning.
5. Register both synchronous operations in action-contract smell enforcement.
6. Implement the JSON codecs and `ReferenceEvidenceJsonContract` with the shared JSON parser and serializer.
7. Update production and test consumers to direct defining leaves.
8. Split the root test using one frozen semantic fixture owner.
9. Remove root exports and delete `reference_evidence.py`; add no facade.
10. Extend hierarchy-smell and clean-wheel presence/removal checks.
11. Prove exact fixture and generated-output replay, then run focused tests, Ruff, Mypy, full pytest, Sphinx warnings-as-errors, lock verification, source/wheel builds, clean-wheel imports, Markdown validation, and `git diff --check`.

## Non-goals

This slice does not move `reference_claim_candidate.py`, `reference_locator.py`,
or transcript-batch modules; change the wire schema or contract status; add
legacy decoding; accept incomplete evidence; infer Workflow lifecycle; perform
I/O; independently re-run audits; approve references; attach assets; publish
content; or preserve unstable Python import paths.
