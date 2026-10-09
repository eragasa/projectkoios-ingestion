# Replicated reading-order evaluation implementation

## Boundary

`LayoutReadingOrderEvaluationRequest` binds:

- exactly one `LayoutReadingOrderCandidate` with at least two unique stable
  layout-element identities;
- one non-empty opaque `search_evidence_id`;
- between two and sixteen contiguous declared replica slots.

The request rejects work before derivation when the worst-case pair/replica
relation count
`replica_count * element_count * (element_count - 1) / 2` exceeds 100,000.
This single bound covers pair comparison and exact contradiction output; the
evaluator never truncates reported pairs.

Each present slot carries one
`LayoutReadingOrderNormalizedReplicaJudgment`. The normalized record binds an
opaque Agent-owned evidence identity, the exact candidate identity, covered
elements, an optional claimed order, and one closed judgment:

- `AGREES_WITH_CANDIDATE`;
- `DISAGREES_WITH_CANDIDATE`;
- `UNRESOLVED`.

The package does not dereference opaque identities and does not inspect Search
chunks, prompts, model/provider metadata, raw responses, or generation quality.
No Search or Agent package is imported.

## Deterministic validation

Normalized element identities use the same 1,024-character bound as the
layout candidate owner; opaque Search and Agent evidence identities retain the
separate 512-character evaluation bound.

A valid agreement judgment must claim the candidate order filtered to its
unique covered elements. A valid disagreement judgment must claim a different
permutation of exactly those covered elements. An unresolved judgment must not
claim an order. Empty identities, wrong candidate bindings, unknown or
duplicate elements, claimed-order coverage mismatch, inconsistent declared
judgments, and duplicate normalized evidence identities are malformed.
Duplicate evidence identities invalidate every duplicate and never increase the
valid replica count. A declared slot without a judgment is missing evidence.

For each valid disagreement, the evaluator derives every claimed precedence
that reverses the candidate. Across valid replicas, it reports every
candidate-oriented element pair for which at least one evidence identity
supports each direction.

## Independent result dimensions

`replica_agreement` is:

- `EXACT_AGREEMENT` only when at least two valid replicas completely cover the
  candidate and have identical normalized judgment semantics;
- `CONSISTENT_PARTIAL` when at least two valid replicas do not contradict each
  other on common asserted precedence but are not in exact complete agreement;
- `DISAGREEMENT` when valid replicas assert opposite precedence for any common
  pair;
- `NOT_EVALUABLE` when fewer than two distinct valid replicas remain.

`aggregate_coverage` is `COMPLETE` only when every declared slot is valid and
covers every candidate element, `NONE` when no valid replica covers an element,
and `PARTIAL` otherwise. Coverage is never collapsed into agreement.

The result also retains sorted distinct considered and valid opaque evidence
identities, per-replica candidate alignment, exact disagreement pairs, missing
slots, malformed evidence with closed reasons, and closed escalation reasons.
The result reconstructs the pure derivation during initialization and rejects
forged fields.

## Conservative stop condition

Escalation is false only when at least two distinct valid replicas completely
cover the candidate and all exactly agree with it. Escalation reasons are drawn
only from:

- `TOO_FEW_DISTINCT_VALID_REPLICAS`;
- `MISSING_EVIDENCE`;
- `MALFORMED_EVIDENCE`;
- `INCOMPLETE_COVERAGE`;
- `UNRESOLVED_JUDGMENT`;
- `REPLICA_DISAGREEMENT`;
- `CANDIDATE_DISPUTED`.

Unanimous replicas that claim the same alternative order produce exact replica
agreement and `CANDIDATE_DISPUTED`; the alternative remains evidence and is not
returned as an accepted, corrected, or final order.

## Exclusions

This boundary performs no retrieval, model or provider invocation, prompt
construction, Workflow lifecycle, retry, budget, timing, majority vote,
weighting, accuracy measurement, candidate ranking, layout correction,
finalization, or publication. Applications may later compose Search and Agent
owners around this pure Ingestion evaluator.
