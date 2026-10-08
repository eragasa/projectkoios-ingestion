# `reference.evidence.json.value`

The immutable `ReferenceEvidenceJsonValueReader` instance composes explicit
evidence value requirements and owns strict access to exact-field mappings,
bounded arrays, text, non-negative integers, booleans, text tuples, and string
enums after shared JSON parsing. It is not a static utility namespace. It
performs no byte parsing, serialization, domain aggregate validation, or error
translation.
