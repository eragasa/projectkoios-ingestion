# Ingestion JSON boundary inventory

The repository contains several different uses of JSON. Only typed durable
record boundaries are `JsonContract` specializations. Presentation and backend
transport remain separate even when they use the standard-library `json`
module.

## Typed durable JSON boundaries

These families have a defined record shape, reconstruction rules, and replay or
verification behavior:

| Current owner | JSON boundary | Current behavior |
|---|---|---|
| `batch.py` | PDF batch plan | Versioned pretty UTF-8 text with terminal newline |
| `ocr/batch/plan.py` | Selective OCR plan | Versioned pretty UTF-8 text with terminal newline |
| `ocr/reconciliation/batch/plan.py` | OCR reconciliation plan | Versioned pretty UTF-8 text with terminal newline |
| `transcript_batch.py` | Transcript batch plan | Strict duplicate rejection, bounded bytes, sorted pretty text |
| `reference/evidence/json/contract.py` | Reference evidence | Strict bounded canonical UTF-8 bytes and complete reconstruction |
| `page_projection.py` | Validation report and owner projection | Compact sorted canonical bytes plus typed loading |
| `cache.py` | Extraction result and cache entry | Strict duplicate/constant rejection and typed reconstruction |
| `integrations/disk/extraction/store.py` | Journal records | Durable line-delimited JSON record transport |
| `storage/extraction/projection/document.py` | Projected document JSON | Rebuildable typed read-model payload |

These boundaries should migrate incrementally to domain-specific
`JsonContract[T]` implementations after byte-for-byte replay evidence is
captured.

## Existing generic JSON behavior

Two root modules already contain de facto shared JSON behavior:

- `identity.py` recursively projects dataclasses, enums, paths, bytes,
  collections, and scalars before compact sorted serialization.
- `serialization.py` exposes generic `serialize_contract()` and
  `contract_dict()` wrappers around that behavior.

Their names obscure JSON ownership and use “contract” without naming the JSON
boundary. Their JSON responsibilities move under `ingestion.json`; SHA-256 and
stable-ID responsibilities remain with their existing owners until separately
reviewed.

## Strict parsing duplicated today

Strict parsing logic is independently implemented in:

- `cache.py`;
- `transcript_batch.py`; and
- `integrations/ollama/multimodal/processor/region/base.py`.

Across those implementations the repository already needs:

- strict UTF-8;
- byte limits before parsing;
- lexical nesting limits before recursive parsing;
- duplicate-object-key rejection;
- `NaN`/`Infinity` rejection;
- integer and float token-length limits;
- finite parsed numbers;
- aggregate node limits;
- per-string and aggregate string-byte limits; and
- root-shape validation.

The shared parser must support these policies without importing Ollama or any
other domain package. Domain owners translate generic failures into their
established failure records and messages.

## JSON uses that are not `JsonContract` specializations

### Command presentation

CLI modules emit transient human/operator summaries with `json.dumps()`. Those
summaries are not durable typed reconstruction boundaries merely because their
presentation format is JSON. They may use `JsonSerializer` for consistent
encoding, but they do not implement `JsonContract[T]` unless an owning contract
is explicitly introduced.

### Backend transport

MongoDB, Ollama, and other integrations parse backend payloads. A backend
response may use `JsonParser`, but it remains an integration-owned transport
boundary. It becomes a `JsonContract[T]` only when it provides complete typed
reconstruction and deterministic serialization for a repository-owned record.

### Internal digest material

Projection inventory digests and stable IDs serialize internal values
canonically. They use `CanonicalJsonSerializer` but do not each create a new
record-specific JSON contract.

## Current formatting families

The inventory identifies three retained formatting profiles:

1. canonical compact, sorted keys, UTF-8, no terminal newline;
2. durable pretty, two-space indentation, UTF-8, terminal newline, with field
   order supplied by the domain; and
3. durable sorted pretty, two-space indentation, UTF-8, terminal newline.

Formatting is explicit contract configuration. No global default may silently
change existing bytes.
