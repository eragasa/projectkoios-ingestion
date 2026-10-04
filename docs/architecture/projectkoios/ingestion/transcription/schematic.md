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
              TranscriptionDerivation
                         │
             ┌───────────┴───────────┐
             ▼                       ▼
      TranscriptionItem      TranscriptionOmission
             └───────────┬───────────┘
                         ▼
          StructuredTranscriptionResult
                         │
          TranscriptionResultValidation
             ┌───────────┼───────────┐
             ▼           ▼           ▼
 source validations  omission     configured
                     coverage       limits
             └───────────┬───────────┘
                         ▼
              proposed evidence only
```

`TranscriptionCacheIdentity` derives from the exact request and processor
identity. It does not publish or persist the result.
