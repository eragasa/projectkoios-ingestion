# `json.parser` implementation

`JsonParser` is immutable and requires one explicit `JsonLimits` value.

## Processing order

1. Accept only `bytes` or `str`.
2. Decode bytes or encode text using strict UTF-8.
3. Reject content above `maximum_utf8_bytes`.
4. Scan the lexical stream once for bounded container depth and balanced
   brackets while respecting quoted strings and escapes.
5. Call `json.loads()` with hooks that reject duplicate object keys,
   non-RFC constants, overlong integer/float tokens, and non-finite floats.
6. Traverse the resulting tree once to enforce aggregate items, depth,
   per-string bytes, aggregate string bytes, finite numbers, and closed
   `JsonValue` types.
7. Return the validated tree without retaining the source buffer.

The parser does not require an object root; root shape belongs to the concrete
`JsonContract`. It does not canonicalize key order, normalize numbers, or
construct domain records.

Malformed syntax and unsupported JSON values raise `JsonParseError`. Resource
exhaustion raises `JsonLimitError`. Duplicate keys and forbidden constants are
parse failures rather than last-value-wins behavior.

Implementation must avoid recursive post-parse traversal and `pop(0)`. Lexical
and tree scans are linear in bounded input size. Tests cover malformed UTF-8,
unbalanced nesting, quoted brackets, duplicate keys, non-finite constants,
oversized numeric tokens, exact limits, limit-plus-one, aggregate node limits,
and deterministic error classification.
