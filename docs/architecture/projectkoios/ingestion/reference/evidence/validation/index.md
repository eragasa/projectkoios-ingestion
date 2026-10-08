# `reference.evidence.validation`

## Owner

`ReferenceEvidenceValueRequirements` binds the explicit domain string ceiling
and applies reusable checks for non-empty valid-UTF-8 text, non-negative
integers excluding booleans and canonical lowercase SHA-256 text. Semantic
inventories own their collection bounds directly.

Records share the immutable `REFERENCE_EVIDENCE_VALUE_REQUIREMENTS` instance.
This is a state-bound requirement value, not a static utility namespace. It does
not parse JSON, serialize values, inspect files, or validate aggregate lineage.
