# `json.limits.error` implementation

`JsonLimitError` is a `ValueError` subclass. It reports which configured bound
was exceeded without retaining the rejected payload.

Parsers, projectors, and serializers use this one generic resource failure.
Concrete domain JSON contracts may translate it to an established domain limit
error while preserving exception chaining. The generic error never imports or
constructs a domain-specific failure.
