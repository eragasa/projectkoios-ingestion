# `json.limits.definition` implementation

`JsonLimits` is a frozen dataclass whose positive integer fields are:

- `maximum_utf8_bytes`;
- `maximum_container_depth`;
- `maximum_items`;
- `maximum_string_bytes`;
- `maximum_total_string_bytes`; and
- `maximum_number_characters`.

Construction rejects booleans, non-integers, non-positive values, and values
above repository hard ceilings. Aggregate string bytes cannot exceed total
UTF-8 bytes, and individual string bytes cannot exceed aggregate string bytes.

Hard-ceiling constants are implementation safety boundaries, not domain wire
limits. Their implemented values are:

- `MAX_JSON_UTF8_BYTES = 1_000_000_000`;
- `MAX_JSON_CONTAINER_DEPTH = 512`;
- `MAX_JSON_ITEMS = 100_000_000`;
- `MAX_JSON_STRING_BYTES = 1_000_000_000`;
- `MAX_JSON_TOTAL_STRING_BYTES = 1_000_000_000`; and
- `MAX_JSON_NUMBER_CHARACTERS = 4_096`.

The byte ceiling covers the inventoried one-gigabyte page-projection artifact
boundary. These are outer repository safety bounds; each external document
family declares substantially narrower operational limits where its schema
permits them.

No implicit `DEFAULT_JSON_LIMITS` value is provided. A caller must make its
resource policy explicit.
