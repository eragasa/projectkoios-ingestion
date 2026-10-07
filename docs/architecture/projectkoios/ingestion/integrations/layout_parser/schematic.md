# LayoutParser integration schematic

```text
isolated model runtime
        │ frozen labels, pixel boxes, confidence
        v
LayoutParserDetection[]
        │
        v
LayoutParserProposalRequest
        │ exact package/backend/model/hash/label-map configuration
        v
LayoutParserRegionProposalActionizer
        │
        v
LayoutParserProposalResult
        ├─ LayoutRegionProposalSource
        └─ LayoutRegionProposal[]
```

Vendor inference is outside this runtime-neutral action boundary.
