# `json.error` implementation

`JsonError` is a `ValueError` subclass and the base for non-limit JSON boundary
failures.

`JsonParseError` reports malformed UTF-8 JSON, forbidden constants, invalid
numeric tokens, unbalanced containers, and unsupported parsed values.
`JsonDuplicateFieldError` is its typed subtype for duplicate object fields so
domain contracts never classify duplicates by matching diagnostic text.

`JsonSerializationError` reports unsupported source values, cycles, invalid
mapping keys, non-finite numbers, and UTF-8/formatter failures.

Errors contain bounded context only and never embed a complete untrusted
payload. `JsonLimitError` remains in `json.limits.error` so callers can classify
resource exhaustion separately.

Concrete domain contracts translate these errors only when an established
domain error is required. Translation retains the generic error as the cause.
