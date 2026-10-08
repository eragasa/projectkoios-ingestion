# `reference.evidence.json.contract`

`ReferenceEvidenceJsonContract` composes the explicit reference-evidence
`JsonLimits`, shared `JsonParser`, canonical `JsonSerializer`, and aggregate
record codec. It owns text/byte entry points, canonical replay, reusable-record
requirements, and translation of shared JSON failures into reference-evidence
parse, serialization, and limit errors. `ReferenceEvidenceRecord` invokes this
specific contract during construction to guarantee that every accepted record
fits its declared reversible wire boundary. The contract still owns exact byte
calculation and owns no nested field schema.
