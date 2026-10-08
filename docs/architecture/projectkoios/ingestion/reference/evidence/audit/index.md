# `reference.evidence.audit`

## Owner

This leaf owns `ReferenceEvidenceAuditScope` and `ReferenceEvidenceAudit`.
Layer values and inventories belong to `layer.py`; audited-artifact identities
belong to `lineage.py`.

## Invariants

Scope is exactly `recorded_producer_derivation_audit` and
`independently_revalidated` is always false. Artifact media type and dependent
contract version are fixed. Audited artifact identities are non-empty, unique,
and bounded. Layer counts are immutable, unique, lexicographically sorted,
bounded, and non-negative. Audit status and finding count are recorded producer
evidence; aggregate pass and coverage requirements belong to the state-bound
verifier in `lineage.py`.
