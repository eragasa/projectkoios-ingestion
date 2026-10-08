# `json.limits.error` implementation

`JsonLimitError` is a `ValueError` subclass. It reports which configured bound
was exceeded without retaining the rejected payload.
`JsonDocumentByteLimitError` is its typed subtype for parser-input and
serializer-output document-byte ceilings. String, item, depth, and numeric
bounds continue to use the base error.

Parsers, projectors, and serializers use these generic resource failures.
Concrete domain JSON contracts may translate them to established domain limit
errors while preserving exception chaining. Typed document-byte classification
prevents contracts from matching diagnostic text. Generic errors never import
or construct a domain-specific failure.
