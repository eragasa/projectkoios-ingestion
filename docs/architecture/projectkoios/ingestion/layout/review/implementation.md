# Layout review and annotation

Layout review preserves disagreement evidence without changing authoritative page
layout results.

```text
PageLayoutResult
    + LayoutPageRenderEvidence
    + LayoutRegionProposalSource
    + LayoutRegionProposal[]
    -> LayoutReviewRequest
    -> DeterministicLayoutReviewActionizer
    -> LayoutReviewCase
    -> external human annotation
    -> LayoutAnnotationCollection
```

## Ownership

- `layout/render/evidence.py` identifies exact rendered page pixels without
  retaining private image bytes.
- `layout/proposal/` owns backend-neutral, explicitly unaccepted semantic-region
  proposals and proposal-source identity.
- `layout/review/` compares native text blocks with proposed pixel regions and
  selects bounded failure-review cases.
- `layout/annotation/` owns human observations, corrected regions, native-block
  membership, reading-order edges, and failure labels.
- `integrations/layout_parser/` converts frozen LayoutParser detections into
  backend-neutral proposals.

Package initializers are ownership markers only. Consumers import defining
leaves directly.

## Authority

`LayoutRegionProposal` is never authoritative. `LayoutReviewCase` is selection
and comparison evidence. `LayoutAnnotationCollection` is human annotation
evidence but does not accept a proposal, replace `PageLayoutResult`, or authorize
publication. A future acceptance operation must own that decision explicitly.

The deterministic page-layout analyzer remains authoritative. Review tooling
observes its warnings and compares its exact native block identities with
external region proposals.

## Bounds and determinism

Requests bind complete immutable configuration, source identities, rendered
image identity, proposal resource identity, and proposal IDs. Review preparation
is bounded by block, proposal, block-proposal comparison, and overlap limits.
Stable IDs include every persisted field that can affect behavior.

Review reasons include baseline ambiguity, baseline warnings, invalid native
geometry, missing proposals, incomplete region coverage, and conflicting region
kinds. Coverage is measured in rendered pixel coordinates as intersection over
native block area.

## Private evidence

Private PDFs, rendered pages, model weights, and annotation images remain outside
the repository. Repository contracts retain only hashes, dimensions, stable
source identities, bounded geometry, and lineage. External annotation tools may
serialize these immutable contracts using the canonical ingestion serializer.
