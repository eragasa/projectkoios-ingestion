# Layout annotation implementation

## Authority and authorship

`PageLayoutResult` remains authoritative layout evidence.
`LayoutRegionProposal` remains unaccepted proposal evidence.
`LayoutReviewCase` remains deterministic comparison evidence.

`LayoutModelAnnotationCandidate` is model-authored evidence. It is not a human
annotation and does not become authoritative merely because it parses or
reaches replicated agreement. `LayoutAnnotationCollection` remains explicit
human annotation evidence. `LayoutHumanFinalReviewEvidence` binds a human
judgment to one exact admitted model resolution without rewriting model output.
No type in this package authorizes publication.

Any later authority transition requires a separately named acceptance operation.
Search or another downstream owner controls projection and chunk eligibility.
Workflow controls whether and when invocations, retries, human review,
approvals, checkpoints, or publication occur.

## Model invocation contract

`LayoutAnnotationModelRequest` binds:

- one exact `LayoutReviewCase`;
- one exact `LayoutAnnotationModelResource`;
- one locator-free `ManagedArtifactReference` matching the case render;
- one case-derived `LayoutAnnotationModelPrompt`;
- one bounded `LayoutAnnotationModelConfiguration`; and
- one replica index.

The prompt retains exact UTF-8 text, byte length, template digest, rendered
prompt digest, response-schema digest, and case identity. Its manifest includes
the authoritative layout-result identity, render identity and image digest,
block review evidence, proposals, geometry, and review reasons.

`LayoutAnnotationModelResource` records provider, model name/version and digest,
and runtime name/version. These are domain values rather than vendor SDK types.

`LayoutAnnotationModelActionizer` is the runtime-neutral invocation port.
Concrete provider integrations must return
`LayoutAnnotationModelInvocationResult`, which retains the exact canonical
non-media request document, exact raw response bytes when present, their digests
and lengths, the bound semantic request, and a provider-neutral outcome. The
request document is reconstructed and compared byte-for-byte. It includes the
exact prompt, schema lineage, model/runtime resource, managed image reference,
sampling values, replica, and render/image identity. The port owns one invocation only. It does not infer
retries or Workflow lifecycle.

Large page-image bytes remain outside the contract. The request document binds
the exact render and image digest; a concrete integration must resolve and
verify bytes through an explicit provider boundary. Provider-specific wire
encoding is integration evidence and must not be confused with the canonical
request document.

## Strict typed parsing

`LayoutModelResponseParser` consumes one invocation. Both the actionizer and
`LayoutModelResponseParsingResult` use the same pure
`LayoutModelResponseInterpreter`, so direct result construction reconstructs
the only valid status, candidate, and limitation from the retained invocation
and exact raw bytes. The interpreter uses the shared strict bounded JSON parser,
so failed invocations, malformed UTF-8, duplicate fields, non-RFC constants,
non-finite numbers, excessive depth/items/strings, and trailing or non-JSON
output fail closed.

The model response has an exact field set:

- schema version and exact case identity;
- one closed annotation outcome;
- corrected regions with kinds, pixel boxes, and native block identities;
- directed reading-order edges; and
- failure annotations with explicit block, proposal, and corrected-region
  references.

Unknown fields and vocabulary are rejected. Region indexes are resolved only
within the same response. Existing annotation validation then checks case
identity, render bounds, native block and proposal references, duplicate use,
reading-order acyclicity, and outcome consistency.

A valid parse yields `LayoutModelAnnotationCandidate`. Unordered reference
arrays and annotation collections are normalized for candidate identity, while
the directed meaning of reading-order edges is preserved. Candidate identity
excludes invocation identity and response formatting, so it represents exact
semantic agreement across replicas. A failed parse yields
`LayoutModelAnnotationLimitation`; it never repairs or silently accepts the
response.

## Replication and agreement

`LayoutModelAnnotationResolutionPolicy` requires at least two invocations and at
least two agreeing valid candidates. `LayoutModelAnnotationResolutionRequest`
requires the exact configured replica count, canonical replica ordering,
distinct invocation identities, and identical case, model resource, prompt,
and invocation configuration.

`LayoutModelAnnotationResolutionActionizer` is pure. It admits a candidate only
when:

1. the minimum valid response count is present;
2. every valid parsed response has the same candidate identity; and
3. the result can reconstruct the exact agreeing invocation set.

A valid conflicting response makes the case unresolved even when another group
meets the numeric threshold. Too few valid responses and conflicting valid
responses produce distinct explicit limitations. Rejected parsing evidence
remains available through the resolution request.

`ADMITTED` means admission into model-resolution evidence only. It does not mean
human affirmation, proposal acceptance, canonical layout authority, projection
eligibility, or publication authorization.

## Optional terminal human review

`LayoutHumanFinalReviewEvidence` has four explicit states:

- `NOT_HUMAN_REVIEWED` — no affirmation or rejection is implied;
- `AFFIRMED` — a named reviewer affirms the exact resolution;
- `CORRECTED` — a named reviewer appends a case-bound
  `LayoutAnnotationCollection` correction; and
- `REJECTED` — a named reviewer rejects the exact resolution.

Reviewed states require a bounded reviewer identity and review-protocol
identity. Correction evidence must be authored by the same reviewer, bind the
same case, and use the correction outcome. Affirmation and rejection cannot
carry correction evidence.

The record is immutable. A correction does not alter the raw response, parsed
candidate, replica evidence, or model resolution. Downstream policy chooses
whether any review state is eligible for later projection.

## Bounds and reconstruction

External text, counts, indexes, numbers, and response sizes are validated before
identity derivation. Derived identities use `init=False`. Direct construction
repeats all invariants. Candidate and resolution results retain their complete
requests, allowing reconstruction to reject substituted cases, prompts,
resources, replicas, candidates, or affected-invocation sets.

No generic metadata bag, vendor object, retry state, approval state, or
publication state enters these contracts. Parsing-result reconstruction rejects
a candidate or limitation classification substituted independently of the raw
response.
