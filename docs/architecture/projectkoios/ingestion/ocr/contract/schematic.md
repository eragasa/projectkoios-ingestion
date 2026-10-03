# OCR contract schematic

```text
OCRRequest
├── OCRConfiguration
└── OCRSelection
    ├── OCRPageImage → RenderedRegion
    └── native-text references

OCRResult
├── exact OCRRequest
├── OCRProcessorIdentity
└── OCRSelectionResult
    ├── OCRToken
    ├── OCRLine
    ├── OCRWarning
    └── OCRFailure
```
