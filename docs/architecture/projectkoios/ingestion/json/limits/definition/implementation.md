# `json.limits.definition` implementation

`JsonLimits` is a frozen dataclass whose positive integer fields are:

- `maximum_utf8_bytes`;
- `maximum_depth`;
- `maximum_items`;
- `maximum_string_bytes`;
- `maximum_total_string_bytes`; and
- `maximum_number_characters`.

Construction rejects booleans, non-integers, non-positive values, and values
above repository hard ceilings. Aggregate string bytes cannot exceed total
UTF-8 bytes, and individual string bytes cannot exceed aggregate string bytes.

Hard-ceiling constants are implementation safety boundaries, not domain wire
limits. Their initial values must cover every inventoried existing boundary,
including the one-gigabyte page-projection artifact ceiling, while preventing
new unbounded configurations. Exact values are selected during implementation
after measuring current fixtures and are documented with the evidence used.

No implicit `DEFAULT_JSON_LIMITS` value is provided. A caller must make its
resource policy explicit.
