# `reference.claim.projection`

This package owns deterministic, synchronous projection of a payload-free claim
candidate from reusable reference evidence, a positive page-location result,
and a bounded claim identity.

- [`request`](request/index.md) owns the immutable input.
- [`actionizer`](actionizer/index.md) owns lineage checking and candidate
  construction.
