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

`TranscriptionRequestValidation` retains the exact request subjects used for
same-document, provenance, geometry, bound, and exact-artifact checks. Source-
specific immutable derivations own page, structure, raw-block, equation, table,
and figure projection. `TranscriptionOrderDerivation` owns ordering evidence,
and `TranscriptionWarningDerivation` owns canonical composition warnings.
There are no free helper functions or private helper methods in the
transcription package.

`TranscriptionResultValidation` retains its subordinate warning, object, and
limit validation records. Object validation retains per-item records from
`source/validation/`, omission coverage from `omission/validation/`, and exact
source coverage. Requests and results expose these records through concrete
`validation` properties. The dependency direction is result to validation;
validators do not import the completed result class. Validation establishes
contract consistency only; it does not assert scientific correctness or human
acceptance.

`TranscriptionCacheIdentity` is an immutable `AbstractIdentity`, not a free
cache-key function. It binds the complete request, contract and configuration
versions, and processor identity.

The former `transcription.py`, `StructuredTranscriptionContract`,
`constants.py`, `TranscriptionInput`, and structured-transcription protocol
alias and `compose()` wrapper have been removed. Item kind, omission reason,
result status, and limit errors live under their noun owners. Package
initializers are empty ownership markers and re-export nothing.

Golden verification preserves request, result, item, and cache identities plus
canonical serialized result bytes.
