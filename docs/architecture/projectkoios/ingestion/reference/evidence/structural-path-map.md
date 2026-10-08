# Reference-evidence structural path map

This is the exact reviewed map for the bounded reference-evidence record and
JSON migration. Paths are repository-relative. Removed paths are not retained
as aliases, compatibility modules, or re-export facades.

## Production source

| Removed path or responsibility | Direct owner path | Ownership |
|---|---|---|
| no package marker | `src/python/projectkoios/ingestion/reference/__init__.py` | Docstring-only reference-domain namespace |
| no package marker | `src/python/projectkoios/ingestion/reference/evidence/__init__.py` | Docstring-only reference-evidence namespace |
| `reference_evidence.py` — `ReferenceEvidenceArtifact` | `reference/evidence/artifact.py` | Exact artifact content identity and byte verification |
| `reference_evidence.py` — `ReferenceEvidenceSource` | `reference/evidence/source.py` | Source blob/hash/size/media identity |
| `reference_evidence.py` — `ReferenceEvidenceExtraction` and extraction media type | `reference/evidence/extraction.py` | Extraction artifact and producer evidence record |
| `reference_evidence.py` — `ReferenceEvidenceTranscript` and clean-transcript media type | `reference/evidence/transcript.py` | Clean-transcript artifact and producer evidence record |
| raw transcript layout-result tuple | `reference/evidence/layout.py` | Ordered semantic layout identity inventory |
| `reference_evidence.py` — `ReferenceEvidenceLayerCount` | `reference/evidence/layer.py` | Audited layer count and ordered semantic inventory |
| raw audited-artifact tuple and aggregate lineage checks | `reference/evidence/lineage.py` | Semantic artifact identity inventory and state-bound lineage verification |
| `reference_evidence.py` — `ReferenceEvidenceAudit`, `ReferenceEvidenceAuditScope`, and audit media type | `reference/evidence/audit.py` | Recorded producer-audit evidence |
| contract/generator metadata | `reference/evidence/definition.py` | Stable wire definitions |
| contract and completeness enums | `reference/evidence/status.py` | Closed aggregate statuses |
| raw completeness-reason tuple | `reference/evidence/completeness.py` | Ordered semantic reason inventory |
| raw limitation tuple and required limitations | `reference/evidence/limitation.py` | Ordered semantic limitation inventory |
| `ReferenceEvidenceRecord.identity_for(**values)` | `reference/evidence/identity.py` | Bounded typed historical identity derivation |
| `ReferenceEvidenceRecord.create()` and aggregate record | `reference/evidence/record.py` | Aggregate immutable evidence result without a construction bypass |
| `reference_evidence.py` — six projection inputs accepted by `build_reference_evidence` | `reference/evidence/projection/request.py` — `ReferenceEvidenceProjectionRequest` | One complete immutable bounded projection request |
| `reference_evidence.py` — extraction/transcript/audit artifact validation | `reference/evidence/projection/artifact.py` | State-bound exact producer-artifact verification |
| `reference_evidence.py` — producer status and cross-source checks | `reference/evidence/projection/lineage.py` | State-bound projection-lineage verification |
| `reference_evidence.py` — `build_reference_evidence` | `reference/evidence/projection/actionizer.py` — `ReferenceEvidenceProjectionActionizer` | Pure action and sole complete-record construction route |
| `reference_evidence.py` — source and optional artifact inputs accepted by `verify_reference_evidence` | `reference/evidence/verification/request.py` — `ReferenceEvidenceVerificationRequest` | One complete immutable bounded verification request |
| raw verified-artifact tuple | `reference/evidence/verification/artifact.py` | Closed artifact kind and schema-ordered semantic inventory |
| `reference_evidence.py` — successful verification has no result value | `reference/evidence/verification/result.py` — `ReferenceEvidenceVerificationResult` | Immutable verified record plus typed optional-artifact coverage |
| `reference_evidence.py` — `verify_reference_evidence` | `reference/evidence/verification/actionizer.py` — `ReferenceEvidenceVerificationActionizer` | Stateless source and optional exact-artifact verification action |
| `reference_evidence.py` — parser/serializer composition, canonical replay, and JSON error translation | `reference/evidence/json/contract.py` — `ReferenceEvidenceJsonContract` | Reversible typed bounded canonical JSON document boundary |
| `reference_evidence.py` — aggregate root JSON projection/reconstruction | `reference/evidence/json/record.py` — `ReferenceEvidenceRecordJsonCodec` | Exact root wire-object schema |
| `reference_evidence.py` — artifact JSON projection/reconstruction | `reference/evidence/json/artifact.py` — `ReferenceEvidenceArtifactJsonCodec` | Exact artifact wire-object schema |
| `reference_evidence.py` — source JSON projection/reconstruction | `reference/evidence/json/source.py` — `ReferenceEvidenceSourceJsonCodec` | Exact source wire-object schema |
| `reference_evidence.py` — extraction JSON projection/reconstruction | `reference/evidence/json/extraction.py` — `ReferenceEvidenceExtractionJsonCodec` | Exact extraction wire-object schema |
| `reference_evidence.py` — transcript JSON projection/reconstruction | `reference/evidence/json/transcript.py` — `ReferenceEvidenceTranscriptJsonCodec` | Exact transcript wire-object schema |
| `reference_evidence.py` — audit JSON projection/reconstruction | `reference/evidence/json/audit.py` — `ReferenceEvidenceAuditJsonCodec` | Exact audit wire-object schema |
| nested layer-count JSON projection/reconstruction | `reference/evidence/json/layer.py` — `ReferenceEvidenceLayerCountJsonCodec` | Exact nested layer-count wire-object schema |
| `reference_evidence.py` — mapping/list/scalar/enum decode helpers | `reference/evidence/json/value.py` — `ReferenceEvidenceJsonValueReader` | Strict shared field access over a closed `JsonValue` tree |
| `reference_evidence.py` — shared scalar, digest, integer, and text checks | `reference/evidence/validation.py` — `ReferenceEvidenceValueRequirements` | State-bound domain scalar requirements without JSON parsing |
| `reference_evidence.py` — `ReferenceEvidenceError`, `ReferenceEvidenceParseError`, and `ReferenceEvidenceVerificationError` | `reference/evidence/error.py` | Domain, wire-parse, and verification failures |
| `reference_evidence.py` — artifact, text, tuple, wire-byte, and JSON resource ceilings | `reference/evidence/limits/definition.py` — `ReferenceEvidenceLimits` | Immutable owner of identity-input, record, artifact, parser, and serializer bounds |
| `reference_evidence.py` — `ReferenceEvidenceLimitError` | `reference/evidence/limits/error.py` | Typed domain resource-limit failure |
| no JSON marker | `reference/evidence/json/__init__.py` | Docstring-only reference-evidence JSON namespace |
| no projection marker | `reference/evidence/projection/__init__.py` | Docstring-only projection-action namespace |
| no verification marker | `reference/evidence/verification/__init__.py` | Docstring-only verification-action namespace |
| no limits marker | `reference/evidence/limits/__init__.py` | Docstring-only limits namespace |
| all reference-evidence imports/exports in `src/python/projectkoios/ingestion/__init__.py` | direct imports from defining `reference/evidence/*.py` leaves | No ingestion-root compatibility facade |
| `src/python/projectkoios/ingestion/reference_evidence.py` | deleted | No legacy module or re-export path |

`transcript_batch.py` remains at its existing path in this slice. Claim and
page-location ownership are migrated by the separately specified
[`reference/claim`](../claim/structural-path-map.md) and
[`reference/page/location`](../page/location/structural-path-map.md) slices.

## Tests

| Removed path or responsibility | Direct owner path | Ownership |
|---|---|---|
| `tests/test__ReferenceEvidence.py` — exact producer graphs and serialized producer artifacts | `tests/projectkoios/ingestion/reference/evidence/fixture/projection.py` — `ReferenceEvidenceProjectionFixture` | Frozen projection-scenario fixture owner |
| `tests/test__ReferenceEvidence.py` — canonical record content, identities, artifacts, and exceptional record scenarios | `tests/projectkoios/ingestion/reference/evidence/fixture/record.py` — `ReferenceEvidenceRecordFixture` | Frozen record-scenario fixture owner |
| `tests/test__ReferenceEvidence.py` — artifact, source, child-record, record identity, completeness, and lineage invariants | `tests/projectkoios/ingestion/reference/evidence/test__ReferenceEvidenceRecord.py` | Immutable record behavior |
| `tests/test__ReferenceEvidence.py` — exact producer-input construction behavior | `tests/projectkoios/ingestion/reference/evidence/test__ReferenceEvidenceProjection.py` | Pure projection behavior |
| `tests/test__ReferenceEvidence.py` — exact bytes, parsing, unknown/duplicate fields, canonical replay, malformed input, and wire limits | `tests/projectkoios/ingestion/reference/evidence/test__ReferenceEvidenceJsonContract.py` | Reversible JSON boundary |
| `tests/test__ReferenceEvidence.py` — consumer source and optional artifact checks | `tests/projectkoios/ingestion/reference/evidence/test__ReferenceEvidenceVerification.py` | Verification boundary |

`tests/test__ReferencePageLocator.py` remains with its primary owner and updates
imports in place. Claim-candidate tests move under their separately documented
[`reference/claim`](../claim/structural-path-map.md) owner. The sanitized fixture
remains at
`tests/fixtures/reference_evidence/complete.json`; moving producer code does not
change fixture bytes.

## Documentation

| New path | Ownership |
|---|---|
| `docs/architecture/projectkoios/ingestion/reference/index.md` | Reference-domain scope and authority boundary |
| `docs/architecture/projectkoios/ingestion/reference/evidence/index.md` | Package scope and module index |
| `docs/architecture/projectkoios/ingestion/reference/evidence/implementation.md` | Invariants, JSON profile, compatibility, migration, and validation |
| `docs/architecture/projectkoios/ingestion/reference/evidence/schematic.md` | Dependency and authority direction |
| `docs/architecture/projectkoios/ingestion/reference/evidence/structural-path-map.md` | Exact old-to-new map |
| `docs/architecture/projectkoios/ingestion/reference/evidence/*/index.md` | Individual planned-module ownership |

## Prohibited compatibility paths

The migration does not create or retain:

```text
src/python/projectkoios/ingestion/reference_evidence.py
src/python/projectkoios/ingestion/reference/evidence/evidence.py
src/python/projectkoios/ingestion/reference/evidence/json.py
src/python/projectkoios/ingestion/reference/evidence/reference_evidence.py
```

`reference/__init__.py`, `reference/evidence/__init__.py`,
`reference/evidence/json/__init__.py`,
`reference/evidence/projection/__init__.py`,
`reference/evidence/verification/__init__.py`, and
`reference/evidence/limits/__init__.py` remain docstring-only and export no
moved names.
