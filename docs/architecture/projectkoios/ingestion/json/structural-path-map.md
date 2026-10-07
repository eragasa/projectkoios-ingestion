# Ingestion JSON structural path map

This map separates shared JSON mechanics from domain record schemas. Removed
paths are not retained as aliases or compatibility re-export facades.

## Shared JSON ownership

| Current path or responsibility | Direct owner path | Ownership |
|---|---|---|
| `identity.py` — `to_json_value()` | `json/value.py` — `JsonValueProjector` | Closed JSON-value projection for immutable values |
| `identity.py` — `canonical_json()` | `json/canonical.py` — `CanonicalJsonSerializer` | Compact sorted deterministic JSON text/bytes |
| `serialization.py` — `serialize_contract()` | `json/canonical.py` — `CanonicalJsonSerializer.serialize_text()` | Canonical serialization with explicit JSON ownership |
| `serialization.py` — `contract_dict()` | `json/canonical.py` — `CanonicalJsonSerializer.project_object()` | Canonical JSON-object projection |
| duplicated lexical nesting scans | `json/parser.py` — `JsonParser` | Pre-parse bounded depth and balance validation |
| duplicated duplicate-key and non-RFC-constant hooks | `json/parser.py` — `JsonParser` | Strict object and scalar parsing |
| duplicated parsed-tree bounds | `json/parser.py` — `JsonParser` | One-pass node, string, depth, and finite-number validation |
| implicit `json.dumps()` option sets in durable boundaries | `json/serializer.py` — `JsonSerializer` | Explicit byte-affecting formatting configuration |
| no common typed JSON boundary | `json/contract.py` — `JsonContract[T]` | Typed value conversion plus parser/serializer composition |
| scattered generic JSON failures | `json/error.py` | Parse and serialization failures |
| scattered JSON hard ceilings | `json/limits/definition.py` and `json/limits/error.py` | Shared absolute bounds and limit failure |

`identity.py` retains stable-ID assembly and SHA-256 delegation. It imports
`CanonicalJsonSerializer` rather than owning JSON conversion. `serialization.py`
is deleted after all consumers import the direct JSON owner.

## First domain specialization

| Current path or responsibility | Direct owner path | Ownership |
|---|---|---|
| `batch.py` — `PdfBatchItem` invariant validation | `pdf/batch/item.py` | Immutable PDF source declaration record |
| `batch.py` — `PdfBatchPlan` invariant validation | `pdf/batch/plan.py` | Immutable ordered bounded plan record |
| `batch.py` — item object decoding, plan JSON parsing, and plan JSON serialization | `pdf/batch/json.py` — `PdfBatchPlanJsonContract` | Exact version-1 PDF batch JSON schema and bytes |
| `batch.py` — resource ceilings | `pdf/batch/limits/definition.py` and `pdf/batch/limits/error.py` | PDF-batch-specific limits |

The concrete `PdfBatchPlanJsonContract` depends on `ingestion.json`; the shared
JSON package does not import PDF batch records.

## Later domain migrations

Each later family receives a separately reviewed concrete specialization and
exact replay evidence:

- `SelectiveOCRPlanJsonContract`;
- `SelectiveOCRReconciliationPlanJsonContract`;
- `TranscriptBatchPlanJsonContract`;
- `ReferenceEvidenceJsonContract`;
- page-projection JSON contracts;
- extraction-cache JSON contracts; and
- extraction-journal/projection JSON contracts.

This document does not assign their final domain paths before their individual
ownership reductions are designed.
