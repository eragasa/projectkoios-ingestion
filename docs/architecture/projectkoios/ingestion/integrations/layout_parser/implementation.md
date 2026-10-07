# LayoutParser integration

The LayoutParser integration is an adaptation boundary for frozen external
inference output. It does not add LayoutParser, PyTorch, model weights, or an
in-process model runner to the Ingestion runtime.

```text
isolated LayoutParser worker
    -> LayoutParserDetection[]
    -> LayoutParserProposalRequest
    -> LayoutParserRegionProposalActionizer
    -> LayoutParserProposalResult
        - LayoutRegionProposalSource
        - LayoutRegionProposal[]
```

## Resource binding

`LayoutParserProposalConfiguration` binds:

- LayoutParser package version;
- backend name and version;
- model resource identity and SHA-256;
- complete backend-label to `LayoutRegionKind` mapping;
- maximum detection count.

Every raw detection binds exact rendered-page identity, original model label,
pixel bounds, confidence, and optional evidence. Unknown labels, stale render
identities, duplicate detections, out-of-bounds geometry, and excessive output
are rejected before adaptation.

## Runtime boundary

Inference remains isolated because released LayoutParser model integrations use
legacy resources and checkpoint loading behavior that are unsuitable for the
Python 3.14 core runtime. An external worker may use a repaired or containerized
runtime, but it must freeze detections before this action executes.

The adapter never imports vendor classes. It converts exact immutable detection
records into backend-neutral, non-authoritative proposals while retaining the
model resource and detection lineage needed for replay and annotation.

## Intended use

LayoutParser proposals can pre-label pages selected by deterministic layout
warnings or disagreement analysis. They must not directly produce
`PageLayoutResult`, infer reading order, or override native block evidence.
