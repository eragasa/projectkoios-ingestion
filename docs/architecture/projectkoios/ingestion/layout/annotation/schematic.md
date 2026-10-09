# Layout annotation schematic

```text
authoritative PageLayoutResult
        + exact LayoutPageRenderEvidence
        + unaccepted LayoutRegionProposal[]
                    │
                    v
             LayoutReviewCase
                    │
                    ├─────────────── human benchmark path
                    │                     │
                    │                     v
                    │          LayoutAnnotationCollection
                    │
                    v
      LayoutAnnotationModelRequest[]
      - exact case / prompt / schema
      - exact model/runtime resource
      - bounded sampling configuration
      - distinct replica index
                    │
          provider integration port
                    │
                    v
 LayoutAnnotationModelInvocationResult[]
 - exact canonical non-media request bytes
 - exact raw response bytes
 - model/prompt/resource lineage
                    │
                    v
       LayoutModelResponseParser[]
          │                    │
          │ valid              │ invalid
          v                    v
LayoutModelAnnotationCandidate  LayoutModelAnnotationLimitation
          │                    │
          └──────────┬─────────┘
                     v
 LayoutModelAnnotationResolutionActionizer
          │                    │
          │ agreement          │ conflict/insufficient
          v                    v
       ADMITTED              UNRESOLVED
          │                    │
          │                    └── explicit limitation; ineligible
          v
LayoutHumanFinalReviewEvidence (optional)
 - NOT_HUMAN_REVIEWED
 - AFFIRMED
 - CORRECTED + new human annotation
 - REJECTED
```

## Authority boundary

```text
PageLayoutResult                         authoritative layout evidence
LayoutRegionProposal                    unaccepted proposal
LayoutReviewCase                        deterministic comparison evidence
LayoutModelAnnotationCandidate          model-authored evidence
ADMITTED model resolution               replicated model evidence only
LayoutAnnotationCollection              human benchmark/correction evidence
LayoutHumanFinalReviewEvidence          optional terminal human judgment
future explicit acceptance operation    only possible authority transition
```

No arrow grants publication authority. Workflow owns invocation topology,
retries, approvals, and whether human review occurs.
