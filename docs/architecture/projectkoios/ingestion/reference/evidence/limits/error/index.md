# `reference.evidence.limits.error`

## Owner

`ReferenceEvidenceLimitError` reports that a reference-evidence record,
producer artifact, parser input, parsed value, or serialized document exceeded
an explicit domain ceiling.

It inherits `ReferenceEvidenceError` and therefore remains a `ValueError`.
Structural, type, digest, schema, lineage, and byte-identity failures retain
their distinct error owners.
