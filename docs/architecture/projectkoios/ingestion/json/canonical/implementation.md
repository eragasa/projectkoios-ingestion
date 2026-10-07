# `json.canonical` implementation

`CanonicalJsonSerializer` composes `JsonValueProjector` with a compact
`JsonSerializer` configured for:

- UTF-8 with `ensure_ascii=False`;
- lexicographically sorted object keys;
- separators `(",", ":")`;
- no indentation; and
- no terminal newline.

It replaces generic JSON responsibilities currently split between
`identity.py` and `serialization.py`. It is a one-way serializer, not a
`JsonContract`, because it cannot infer how to reconstruct an arbitrary source
type from a JSON tree.

## Public operations

- `serialize_text(value: object) -> str`
- `serialize_bytes(value: object) -> bytes`
- `project(value: object) -> JsonValue`
- `project_object(value: object) -> dict[str, JsonValue]`

`project_object()` requires an object root and replaces the imprecisely named
`contract_dict()` helper. The class does not parse arbitrary external records;
record-specific parsing belongs to a concrete `JsonContract[T]`.

Stable-ID owners use `serialize_bytes()` and pass those exact bytes to
`SHA256Fingerprinter`. This module does not compute hashes or assemble identity
namespaces.

## Compatibility gate

Before migration, every existing caller of `canonical_json()`,
`serialize_contract()`, and `contract_dict()` is replayed through both paths.
Accepted inputs must produce byte-identical output. Inputs newly rejected for
non-string mapping keys, collisions, cycles, non-finite values, or exceeded
bounds require evidence that no existing stable identity or published artifact
uses them. Otherwise the stricter behavior is a separately versioned change.
