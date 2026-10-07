# `json.value` implementation

`JsonValue` is the recursive closed union of `null`, booleans, integers, finite
floats, strings, arrays, and string-keyed objects.

`JsonValueProjector` replaces the recursive conversion currently owned by
`identity.to_json_value()`. It supports reviewed immutable inputs:

- concrete dataclass instances in declared field order;
- enum values through their underlying value;
- `Path` values as strings;
- bytes as the established `{"hex": "..."}` object;
- tuples and lists as arrays;
- string-keyed mappings as objects; and
- JSON scalar values.

Projection rejects unsupported objects, non-string mapping keys, key collisions,
non-finite floats, cycles, and configured depth/item/string limits before a
serializer or stable-ID hash consumes the result. Signed zero normalization is
owned by the domain value when identity semantics require it; the generic
projector does not alter valid numbers.

The projector performs no JSON text parsing or formatting and imports no domain
record. It raises `JsonSerializationError` for unsupported values and
`JsonLimitError` for resource exhaustion.
