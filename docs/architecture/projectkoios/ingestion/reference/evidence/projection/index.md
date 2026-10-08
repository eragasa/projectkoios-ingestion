# `reference.evidence.projection`

This package owns the single typed synchronous action that constructs complete
reference evidence from exact already-produced inputs.

- [`request`](request/index.md) — immutable extraction, transcript, audit, and exact-artifact inputs.
- [`artifact`](artifact/index.md) — state-bound exact producer-artifact verification.
- [`lineage`](lineage/index.md) — state-bound producer lineage verification.
- [`actionizer`](actionizer/index.md) — deterministic sole complete-record projection route.

`ReferenceEvidenceRecord` is the immutable action result and remains owned by
`reference.evidence.record`. The package initializer is docstring-only.
