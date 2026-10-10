# Page-projection evidence enrichment schematic

```text
PageProjectionResult
  exact page/block/source/result bindings
  current canonical reading evidence
                 |
                 v
PageProjectionEvidenceEnrichmentRequest
                 |
                 v
PageProjectionEvidenceEnrichmentActionizer (pure)
                 |
                 v
PageProjectionEvidenceEnrichmentResult
  one entry per projected source_evidence_id
                 |
       +---------+---------+
       |                   |
       v                   v
paragraph / heading     figure caption
exact raw text          unavailable disposition
SHA-256                 no invented raw pair
source spans            exact cross-bindings
warnings/limitations    applicable limitations
```

The output is sanitized producer evidence, not Search admission, bibliographic
authority, claim support, or publication evidence.
