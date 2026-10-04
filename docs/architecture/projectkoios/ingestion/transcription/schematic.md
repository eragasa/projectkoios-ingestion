# Structured transcription schematic

```text
exact extracted document + complete typed evidence
                         │
                         ▼
          StructuredTranscriptionRequest
                         │
          TranscriptionRequestValidation
                         │
                         ▼
  DeterministicStructuredTranscriptionComposer
                         │
       source-specific derivations (once)
                         │
             ┌───────────┴───────────┐
             ▼                       ▼
      TranscriptionItem      TranscriptionOmission
             └───────────┬───────────┘
                         ▼
          StructuredTranscriptionResult
                         │
          TranscriptionResultValidation
       (links, coverage, warnings, order, limits)
                         │
                         ▼
              proposed evidence only
```

`TranscriptionInputArtifactInventory` supplies compact input identity and byte
accounting. `TranscriptionCacheIdentity` derives from the exact request and
processor identity. Neither publishes or persists the result.
