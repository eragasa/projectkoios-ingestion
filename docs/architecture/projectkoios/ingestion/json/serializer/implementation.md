# `json.serializer` implementation

`JsonSerializer` is a frozen configuration and formatter. Construction requires
explicit values for every byte-affecting choice:

- `ensure_ascii`;
- `sort_keys`;
- `indent` or compact mode;
- compact separators when indentation is absent;
- terminal newline presence; and
- `JsonLimits`.

It accepts only a closed `JsonValue`. Before calling `json.dumps()` it performs
one bounded validation pass for cycles, depth, items, strings, and finite
numbers. It encodes the result using strict UTF-8, adds the configured terminal
newline, then rejects output above `maximum_utf8_bytes`.

The serializer exposes explicit text and byte methods. Both methods represent
the same bytes: the text method is the strict UTF-8 decoding of the byte method.
It does not infer “canonical” or “pretty” behavior from a caller or record type.

The module provides reviewed constructors for the three inventoried formatting
profiles, but each concrete `JsonContract` still declares which profile it
uses. A profile constructor is formatting reuse, not a wire schema.

Serialization failures raise `JsonSerializationError`; output resource failures
raise `JsonLimitError`. The serializer does not hash, publish, or write content.
