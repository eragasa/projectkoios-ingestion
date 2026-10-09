# Layout review schematic

```text
                         authoritative
                       PageLayoutResult
                              │
                              │ exact source/page relation
                              v
renderer evidence ──> LayoutReviewRequest <── LayoutRegionProposalSource
       │                      ^                         │
       │                      │                         │
       v                      │                         v
LayoutPixelMapping     LayoutRegionProposal[] <── frozen adapter result
       │                      │
       └──────────┬───────────┘
                  v
     DeterministicLayoutReviewActionizer
                  │
                  │ one bounded proposal scan per native block
                  v
       LayoutBlockReviewEvidence[]
       - mapped pixel box or invalid geometry
       - positive overlaps
       - significant proposal IDs
       - covered/uncovered/invalid status
                  │
                  v
          LayoutReviewCase
          - complete request
          - ordered block evidence
          - coverage and reasons
                  │
                  ├──> external human annotation
                  │        └──> LayoutAnnotationCollection
                  │
                  └──> model annotation resolution
                           └──> layout.annotation model evidence
```

## Authority boundary

```text
PageLayoutResult                         authoritative layout evidence
LayoutRegionProposal                    unaccepted proposal
LayoutReviewCase                        deterministic comparison evidence
LayoutModelAnnotationResolutionResult   replicated model evidence only
LayoutAnnotationCollection              human benchmark evidence
LayoutHumanFinalReviewEvidence          optional human judgment
future explicit acceptance operation    only possible authority transition
```

No edge in this schematic grants proposal acceptance, publication authority, or
Workflow lifecycle state.
