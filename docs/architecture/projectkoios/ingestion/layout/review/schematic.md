# Layout review schematic

```text
PageLayoutResult ───────────────┐
LayoutPageRenderEvidence ───────┼─> LayoutReviewRequest
LayoutRegionProposalSource ─────┤          │
LayoutRegionProposal[] ─────────┘          v
                           DeterministicLayoutReviewActionizer
                                           │
                                           v
                                  LayoutReviewCase
                                           │
                              external human annotation
                                           │
                                           v
                              LayoutAnnotationCollection
```

No edge in this schematic grants proposal acceptance or publication authority.
