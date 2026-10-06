# Figure-relevance implementation

The runtime-neutral action boundary is:

```text
FigureRelevanceRequest
    → FigureRelevanceProcessor
    → FigureRelevanceResult
```

The processor is a nominal abstract boundary. Implementations produce
question-specific proposals; they do not accept relevance, change source
facts, select workflow topology, or infer lifecycle state.

A request retains the exact review question, ordered candidate selections, and
bounded configuration. A selection resolves exactly one candidate from one
complete detection result. Configuration owns score thresholds and explicit
limits for selections, detection results, input evidence, rendered pixels,
rationale, warnings, failures, resources, metadata, identities, and retained
result size.

A completed selection result contains one proposal. Partial and failed results
retain explicit warnings and failures. Proposals retain the score method,
optional confidence method, rationale, exact component and association
identities, and immutable evidence metadata. These records remain proposals and
never imply review, acceptance, or index eligibility.

Processor identity retains the processor, backend, and bounded resource
identities. The cache identity covers the request and complete processor
identity. Identity derivations have direct leaves under `identity/`; validation
is split by request, proposal, selected candidate, aggregate result, and shared
bounded values. The former static utility container no longer obscures those
owners.

All concrete records remain frozen dataclasses. Stable namespaces, identity
inputs, field order, contract versions, validation behavior, and serialized
bytes are preserved. Package initializers are docstring-only ownership markers
and re-export nothing. The complete reviewed inventory is the
[structural path map](structural-path-map.md).
