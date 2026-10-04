# Structured transcription implementation

The concrete action boundary is:

```text
StructuredTranscriptionRequest
    → DeterministicStructuredTranscriptionComposer
    → StructuredTranscriptionResult
```

There is no protocol alias, request alias, root re-export, compatibility
facade, or `compose()` wrapper.

`AbstractTranscriptionDataObject` owns contract versions, hard bounds,
normalization, primitive immutable-value checks, exact source-span validation,
deduplication, and retained-size accounting. Concrete records own domain
behavior through `create()`, `derive()`, or `validate()` constructors.

`TranscriptionRequestValidation` is the single request trust-boundary
validator. It checks same-document provenance, canonical block identities,
source links, bounds, geometry, and exact artifact-byte accounting. Its result
retains only stable source identities, bounded counts, the artifact inventory
identity, and byte totals; it does not retain the request graph.

`DeterministicStructuredTranscriptionComposer` invokes each source-specific
derivation once, orders the resulting drafts, and creates immutable items,
omissions, and warnings. Page-anchor identity is owned by
`PageTranscriptionDerivation`. Structure disposition is derived once and passed
to structure transcription. Native source evidence is never replaced.

`TranscriptionResultValidation` is the single result trust-boundary validator.
It checks item, omission, warning, source, order, coverage, and limit relations
directly. It does not recreate producer derivations and does not build a graph
of subordinate validation records. Its result retains only the result and
request identities, compact item/omission/warning set identities, and bounded
counts. Validation establishes contract consistency, not scientific
correctness or human acceptance.

`TranscriptionInputArtifactInventory` is an immutable compact derivation. It
retains ordered rendered-region and embedded-artifact identities plus rendered,
embedded, mask, and total byte counts. It deduplicates shared artifact evidence
by canonical artifact identity and retains no equation, table, or figure result
graphs.

Concrete modules live directly under `transcription/`; only the related
source-specific derivation family is grouped under `transcription/derivation/`.
Package initializers are empty ownership markers and re-export nothing. There
are no transcription free helper functions, private helper methods, static
utility methods, local imports, or `TYPE_CHECKING` import escapes.

Golden verification preserves request, result, item, cache, and serialized
result identities.
