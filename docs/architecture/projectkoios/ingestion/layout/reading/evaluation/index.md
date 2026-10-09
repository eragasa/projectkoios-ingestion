# `projectkoios.ingestion.layout.reading.evaluation`

This package owns the pure deterministic evaluation boundary for
already-normalized replicated judgments about exactly one reading-order
candidate.

It reports agreement, coverage, candidate alignment, missing and malformed
evidence, exact pairwise disagreement, and escalation. It does not retrieve
evidence, invoke a model, choose among candidates, correct an order, claim
accuracy, or grant finalization or publication authority.

See [implementation](implementation.md), [schematic](schematic.md), and the
[structural path map](structural-path-map.md).
