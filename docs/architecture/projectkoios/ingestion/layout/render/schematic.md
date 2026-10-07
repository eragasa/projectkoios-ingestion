# Layout render evidence schematic

```text
renderer-owned geometry
    - requested source bounds
    - effective source bounds
    - pixel-to-source affine transform
    - rounding convention
    - page rotation
    - raster dimensions
              │
              v
      LayoutPixelMapping
              │
exact image SHA-256 + renderer/backend/configuration identity
              │
              v
   LayoutPageRenderEvidence
              │
              ├──────────────┐
              │              │
              v              v
LayoutRegionProposal[]   PageLayoutResult
              │              │
              └──────┬───────┘
                     v
            LayoutReviewRequest
```

The render does not derive from or grant authority to `PageLayoutResult`.
`LayoutReviewRequest` owns their exact source-page relation.
