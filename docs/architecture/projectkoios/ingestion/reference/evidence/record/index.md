# `reference.evidence.record`

## Owner

This leaf owns `ReferenceEvidenceRecord`, the immutable
`AbstractDataObjectActionResult` of reference-evidence projection. It owns no
contract definitions, collection primitives, projection constructor, or generic
identity helper.

## Invariants

Construction requires semantic completeness and limitation inventories plus
validated child records. `identity.py` validates every non-ID field, complete
lineage, and the canonical identity-input byte ceiling before deriving the
historical identity; the record checks that exact identity. Complete-lineage
relationships belong to `lineage.py`.

After identity validation, construction invokes the record's explicit
`ReferenceEvidenceJsonContract` to assert the exact canonical wire-byte
ceiling. The import is local because the JSON codec reconstructs this record;
the dependency is intentionally limited to enforcing the declared reversible
boundary. The record does not implement or generalize `JsonContract`.

`require_reusable()` rejects incomplete or unsupported evidence and rechecks
complete lineage without expanding authority. JSON shape, parsing,
serialization, and exact byte calculation remain owned by `json/`.
