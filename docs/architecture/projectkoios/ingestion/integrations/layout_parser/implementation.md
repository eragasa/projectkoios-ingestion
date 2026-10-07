# LayoutParser integration architecture

Status: implemented on the unmerged layout-review branch. The adapter remains
dependency-free and does not run inference; publication awaits fresh review.

The LayoutParser integration adapts frozen external detection evidence into
backend-neutral, non-authoritative layout proposals. It does not add
LayoutParser, PyTorch, model weights, or an in-process model runner to the
Ingestion runtime.

```text
isolated LayoutParser worker
    -> LayoutParserDetection[]
    -> LayoutParserProposalRequest
    -> LayoutParserRegionProposalActionizer
    -> LayoutParserProposalResult
        - complete request
        - exact LayoutRegionProposalSource
        - one LayoutParserProposalAdaptation per detection
```

## Resource binding

`LayoutParserProposalConfiguration` binds:

- LayoutParser package version;
- backend name and version;
- exact model resource identity and SHA-256;
- complete backend-label to `LayoutRegionKind` mapping;
- label-map and label-text bounds; and
- maximum detection count.

Configuration identity includes every field. Label maps are immutable, unique,
sorted, and bounded before hashing.

Every `LayoutParserDetection` binds exact rendered-page identity, original model
label, pixel bounds, and confidence. It accepts no generic metadata or optional
key/value evidence bag. Unknown labels, stale render identities, duplicate
detections, out-of-bounds geometry, and excessive output are rejected before
adaptation.

## Exact derivation

`LayoutParserProposalAdaptation`, defined in
`integrations/layout_parser/adaptation.py`, binds one detection identity to one
backend-neutral `LayoutRegionProposal`.

`LayoutParserProposalResult` retains:

- the complete immutable request;
- the proposal source derived from that request's configuration;
- adaptations in exact request-detection order;
- actionizer name and version; and
- stable result identity.

The result does not accept arbitrary caller-supplied proposal sources or proposal
tuples. Construction derives them from the request. Reconstruction validates:

- one adaptation for every detection;
- exact order and unique detection identities;
- no omitted, duplicated, substituted, or extra proposal;
- proposal kind equal to the configured label mapping;
- proposal pixel box and confidence equal to the detection;
- proposal render identity equal to the request render;
- proposal source equal to the exact package/backend/model/configuration
  resource; and
- detection lineage retained by the typed adaptation relation.

The result may expose proposals as a computed ordered view of adaptations. The
adaptations, not a second independent proposal tuple, are the serialized source
of truth.

## Runtime boundary

Inference remains isolated because released LayoutParser model integrations use
legacy resources and checkpoint loading behavior unsuitable for the Python 3.14
core runtime. An external worker may use a repaired or containerized runtime,
but must freeze detections and exact render evidence before this action executes.

The adapter imports no vendor classes. Vendor-specific records remain under
`integrations.layout_parser`; `layout.proposal` receives only backend-neutral
proposal contracts.

No unsafe `torch.load(..., weights_only=False)` compatibility shim enters the
repository or production runtime.

## Bounds

`integrations/layout_parser/limits/definition.py` owns adapter-specific hard
limits, including label-map count, per-label length, aggregate label-map text,
and aggregate detection-label text. Shared identity-field limits belong to
`layout/limits/definition.py`; proposal count limits belong to
`layout/proposal/limits/definition.py`.

All external strings, mappings, boxes, scores, and counts are checked before
canonical serialization or stable-ID hashing. Resource binding and detection
lineage use explicit fields rather than arbitrary metadata.

## Intended use

LayoutParser proposals may pre-label pages selected by deterministic layout
warnings or disagreement analysis. They must not directly produce
`PageLayoutResult`, infer reading order, override native block evidence, or
create publication authority.

The useful boundary is:

```text
frozen vendor evidence
    -> exact typed derivation
    -> backend-neutral proposal
    -> deterministic review comparison
    -> external human annotation
```

## Replay requirements

Tests must reject stale and cross-request sources, omitted detections, duplicate
adaptations, reordered adaptations, wrong label mappings, altered confidence or
geometry, and stale stable IDs. Equivalent requests must serialize to identical
proposal-source, adaptation, proposal, and result bytes.
