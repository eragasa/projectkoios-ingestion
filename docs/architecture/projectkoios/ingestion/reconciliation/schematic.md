# OCR reconciliation schematic

```text
OCRReconciliationRequest
├── exact OCRResult
├── selected native page (optional)
├── exact layout result (required with native references)
└── OCRReconciliationConfiguration
          │
          ▼
DeterministicOCRReconciler
          │
          ▼
OCRReconciliationResult
├── native stream
├── OCR stream
├── deterministic matches and warnings
└── unaccepted proposed merged stream
```
