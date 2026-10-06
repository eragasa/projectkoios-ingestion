# Transcription structural path map

This is the reviewed source inventory for the transcription hierarchy
migration. Paths are relative to `src/python/projectkoios/ingestion`. Removed
paths are not retained as aliases or re-export facades.

| Removed path | Direct owner path |
|---|---|
| `transcription/artifact_inventory.py` | `transcription/inventory/input/artifact.py` |
| `transcription/cache_identity.py` | `transcription/cache/identity.py` |
| `transcription/composer.py` | `transcription/composer/deterministic.py` |
| `transcription/evidence_status.py` | `transcription/status/evidence.py` |
| `transcription/item_kind.py` | `transcription/kind/item.py` |
| `transcription/limit_error.py` | `transcription/limits/error.py` |
| `transcription/omission_reason.py` | `transcription/reason/omission.py` |
| `transcription/order_status.py` | `transcription/status/order.py` |
| `transcription/request_validation.py` | `transcription/validation/request.py` |
| `transcription/result_status.py` | `transcription/status/result.py` |
| `transcription/result_validation.py` | `transcription/validation/result.py` |
| `transcription/source_object_kind.py` | `transcription/kind/source/object.py` |
| `transcription/structured_request.py` | `transcription/request/structured.py` |
| `transcription/structured_result.py` | `transcription/result/structured.py` |
| `transcription/derivation/raw_block.py` | `transcription/derivation/block/raw.py` |
| `transcription/derivation/structure_disposition.py` | `transcription/derivation/disposition/structure.py` |
| `transcription/derivation/transcription.py` | `transcription/derivation/model.py` |

## Semantic review

- The action boundary is explicit at `request/structured.py`,
  `composer/deterministic.py`, and `result/structured.py`.
- Qualified records are grouped role-first under `status/`, `kind/`, `reason/`,
  `validation/`, and `derivation/`.
- The domain's bounded error uses the plural `limits/` owner. Hard ceilings
  remain class-level invariants of `AbstractTranscriptionDataObject`; this
  structural change does not relocate or alter them.
- `TranscriptionInputArtifactInventory` lives under
  `inventory/input/artifact.py` but remains a pure in-memory derived summary. It
  does not become an external Inventory action and introduces no new inventory
  abstraction.
- `TranscriptionDerivation` uses `derivation/model.py` because it is the common
  immutable derivation record rather than a source-specific variant.
- Package initializers are docstring-only ownership markers. Consumers import
  definitions from their direct leaves; no compatibility facade is retained.
- Transcript-batch discovery, Pipeline design, Workflow orchestration, contract
  fields, field order, stable identity inputs, serialized bytes, evidence
  boundaries, and acceptance semantics are unchanged.
