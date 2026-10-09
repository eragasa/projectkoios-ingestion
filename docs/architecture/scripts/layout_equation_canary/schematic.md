# Layout-equation canary schematic

```text
exact private source and rendered page
        │
        v
pinned detector invocation
        │
        v
strict detector-output parsing
        ├─ invalid ───────────────> downstream NOT_EVALUATED
        │
        v
generic COCO region admission
        │
        └─ Formula category
              ├─ escalation_required ──> downstream NOT_EVALUATED
              ├─ empty ─────────────────> verified zero-formula evaluation
              └─ admitted
                    │
                    v
              equation projection
                    │
                    v
              verified source-region assembly
                    │
                    v
              typed recognition proposals
                    │
                    v
              page stage evidence
                    │
                    v
              re-derived coverage summary
                    │
                    v
              strict independent document verification
```

Neither category admission nor syntactically valid LaTeX or MathML establishes
semantic correctness, whole-page finalization, or publication authority.
