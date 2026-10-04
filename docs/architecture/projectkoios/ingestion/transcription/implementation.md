# Structured transcription implementation

The action boundary is:

```text
StructuredTranscriptionRequest
    → DeterministicStructuredTranscriptionComposer
    → StructuredTranscriptionResult
```

All three are concrete. No protocol alias, request alias, root re-export, or
compatibility facade is retained.

`AbstractTranscriptionDataObject` owns contract versions, hard bounds,
normalization, primitive immutable-value checks, exact source-span validation,
deduplication, and retained-size accounting. Concrete request, result, item,
omission, derivation, validation, and cache-identity records inherit the
nominal transcription role.

`TranscriptionRequestValidation` records completed same-document, provenance,
geometry, bound, and exact-artifact checks. `TranscriptionDerivation` retains
the evidence used to propose page anchors, structure items, raw-block fallbacks,
equations, tables, and figures. `TranscriptionResultValidation` coordinates
final link and status checks; `TranscriptionResultObjectValidation`,
`TranscriptionWarningValidation`, and `TranscriptionResultLimitValidation`
retain completed object-coverage, warning, and configured-bound checks.
Validation establishes
contract consistency only; it does not assert scientific correctness or human
acceptance.

`TranscriptionCacheIdentity` is an immutable `AbstractIdentity`, not a free
cache-key function. It binds the complete request, contract and configuration
versions, and processor identity.

The former `transcription.py`, `StructuredTranscriptionContract`,
`constants.py`, `TranscriptionInput`, and structured-transcription protocol
alias have been removed. Package initializers are ownership markers.

Golden verification preserves request, result, item, and cache identities plus
canonical serialized result bytes.
