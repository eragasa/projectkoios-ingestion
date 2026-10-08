# `projectkoios.ingestion.reference.evidence`

This package owns the immutable Proposed reference-evidence projection, exact
artifact and lineage records, deterministic construction and verification, and
the reversible bounded JSON wire boundary.

## Planned modules

- [`artifact`](artifact/index.md) — digest, media type, byte length, and exact-byte verification for one bound artifact.
- [`definition`](definition/index.md) — stable contract and generator identifiers.
- [`status`](status/index.md) — closed contract and completeness statuses.
- [`completeness`](completeness/index.md) — semantic completeness-reason inventory.
- [`limitation`](limitation/index.md) — semantic evidence-limitation inventory.
- [`identity`](identity/index.md) — bounded historical record-ID derivation.
- [`layout`](layout/index.md) — ordered transcript layout lineage.
- [`lineage`](lineage/index.md) — audit-artifact lineage and complete-lineage verification.
- [`layer`](layer/index.md) — audited layer counts and their inventory.
- [`source`](source/index.md) — source blob, digest, size, and media identity.
- [`extraction`](extraction/index.md) — extraction artifact and producer evidence.
- [`transcript`](transcript/index.md) — clean-transcript artifact, identity, lineage, and producer evidence.
- [`audit`](audit/index.md) — recorded producer-audit evidence.
- [`record`](record/index.md) — aggregate invariants and reusable-evidence policy.
- [`projection`](projection/index.md) — immutable request and stateless actionizer for pure construction from exact already-produced artifacts.
- [`verification`](verification/index.md) — immutable request/result and stateless actionizer for consumer-known source and optional exact-artifact verification.
- [`json`](json/index.md) — `ReferenceEvidenceJsonContract` and exact canonical bytes.
- [`validation`](validation/index.md) — configured bounded scalar requirements used by immutable values.
- [`error`](error/index.md) — domain, parse, and verification failures.
- [`limits`](limits/index.md) — record, artifact, and wire bounds plus typed limit failure.
- `implementation.md` — ownership, invariants, compatibility, and migration sequence.
- `schematic.md` — dependency and authority boundaries.
- `structural-path-map.md` — exact old-to-new source, test, and documentation paths.

Every package initializer is a docstring-only ownership marker. Consumers
import from defining leaves; no root or package compatibility facade is added.
