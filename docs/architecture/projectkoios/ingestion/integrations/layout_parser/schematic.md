# LayoutParser integration schematic

```text
isolated model runtime
        │ frozen label, pixel box, confidence, render ID
        v
LayoutParserDetection[]
        │
        v
LayoutParserProposalRequest
        ├─ exact LayoutPageRenderEvidence
        └─ package/backend/model/hash/label-map configuration
        │
        v
LayoutParserRegionProposalActionizer
        │ deterministic one-to-one adaptation
        v
LayoutParserProposalResult
        ├─ complete request
        ├─ exact LayoutRegionProposalSource
        └─ LayoutParserProposalAdaptation[]
              ├─ detection_id
              └─ LayoutRegionProposal
```

```text
LayoutParserProposalAdaptation[]
        │ computed proposal view
        v
backend-neutral LayoutRegionProposal[]
        │
        v
LayoutReviewRequest
```

Vendor inference, model loading, retries, and resource acquisition remain
outside this runtime-neutral action boundary. Proposals remain unaccepted.
