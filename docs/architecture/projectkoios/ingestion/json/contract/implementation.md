# `json.contract` implementation

`JsonContract[T]` is an abstract generic class for one complete typed JSON
document boundary. It is not an Ingestion Base action and does not add request,
result, identity, evidence, or configuration fields to `T`.

## Required specialization

A concrete contract supplies:

- one immutable `JsonParser`;
- one immutable `JsonSerializer`;
- `to_json_value(value: T) -> JsonValue`;
- `from_json_value(value: JsonValue) -> T`; and
- whether parsing must prove canonical byte replay.

The generic class supplies final public operations for text and bytes:

- `serialize_text(value: T) -> str`;
- `serialize_bytes(value: T) -> bytes`;
- `parse_text(content: str) -> T`; and
- `parse_bytes(content: bytes) -> T`.

Parsing first produces a bounded `JsonValue`, then reconstructs `T`. Record
constructors remain responsible for domain invariants. If canonical replay is
required, the reconstructed record is serialized once and the exact bytes are
compared with the original input.

## Generic boundary

The abstraction exists because the repository already has multiple concrete
families with the same lifecycle: bounded parse, closed value tree, typed
reconstruction, deterministic serialization, and optional replay proof. It is
not inferred from PDF batch alone.

A concrete class name always includes its record and JSON role, such as
`PdfBatchPlanJsonContract`. Domain packages own concrete schemas and error
translation. No registry, reflection, discriminator lookup, or automatic
contract inference is provided.

The class is stateless after construction. Parser and serializer configuration
are immutable. Implementations must not retain parsed payloads or mutable record
state.
