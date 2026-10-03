# Selective OCR reconciliation batch schematic

```text
SelectiveOCRReconciliationPlan
  │
  ├── exact extraction.json SHA-256
  ├── exact SelectiveOCRPublication SHA-256
  └── explicit page
          │
          ▼
strict typed OCR reconstruction
          │
          ▼
OCRReconciliationRequest
          │
          ▼
DeterministicOCRReconciler
          │
          ▼
SelectiveOCRReconciliationPublication
          │
          └── private create-once result.json
```

The flow has no OCR, rendering, replacement-text, transcript, Search, embedding,
or index effect.
