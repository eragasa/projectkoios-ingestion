# Processing-state storage implementation

`AbstractProcessingStateStore` exposes three explicit operations:

- `initialize()` creates missing registration rows and rejects queue geometry
  that differs from an existing registration;
- `load()` returns one canonical `ProcessingStateSnapshot`; and
- `save()` performs an optimistic transition from an exact prior snapshot ID.

A snapshot contains canonically ordered book, chunk, and candidate records. Its
stable identity includes every checkpoint value and artifact locator. Contract
validation requires complete contiguous chunk coverage, valid candidate-to-
chunk linkage, unique keys, bounded inventories, and exact candidate totals.

A save cannot change registered book or chunk geometry. Concurrent or stale
conflicting writes fail with `ProcessingStateConflictError`. Exact replay is
idempotent. Event drafts have stable identities, so retrying a committed save
cannot duplicate events.

The boundary is a disposable operational checkpoint, not source or extraction
evidence authority. Artifact bytes remain under their owning ingestion paths.
