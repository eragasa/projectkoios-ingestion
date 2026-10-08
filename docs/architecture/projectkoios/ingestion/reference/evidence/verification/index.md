# `reference.evidence.verification`

This package owns the single typed synchronous action that verifies reusable
reference evidence against consumer-known source identity and optional exact
producer artifacts.

- [`request`](request/index.md) — immutable expected source and optional artifact inputs.
- [`artifact`](artifact/index.md) — closed artifact kinds and their schema-ordered semantic inventory.
- [`result`](result/index.md) — immutable verified record and typed artifact coverage.
- [`actionizer`](actionizer/index.md) — stateless deterministic verification.

The package initializer is docstring-only. The action performs no I/O and does
not establish semantic accuracy, acceptance, rights, or publication authority.
