# Replicated reading-order evaluation schematic

```text
one candidate_order_id + ordered unique element IDs
                           |
one opaque search_evidence_id
                           |
declared replica slots ----+
    | missing              |
    | malformed normalized |
    | valid normalized     |
    v                      v
             pure deterministic evaluator
                 |       |       |
                 v       v       v
             agreement coverage alignments
                 |       |       |
                 +--- exact pair disagreements
                 +--- missing/malformed evidence
                 +--- closed escalation reasons
                              |
              +---------------+---------------+
              |                               |
all declared replicas valid,         any limitation, dispute,
complete, distinct, and exactly      disagreement, or unresolved
agree with the candidate             judgment
              |                               |
              v                               v
 escalation_required = false         escalation_required = true
```

No path emits a winning, corrected, accepted, selected, or final order.
