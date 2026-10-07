# Layout review and annotation architecture

Status: implemented on the unmerged layout-review branch. Publication remains
pending complete validation and fresh independent review.

Layout review preserves disagreement evidence without changing authoritative
page-layout results.

```text
PageLayoutResult
    + LayoutPageRenderEvidence(LayoutPixelMapping)
    + LayoutRegionProposalSource
    + LayoutRegionProposal[]
    -> LayoutReviewRequest
    -> DeterministicLayoutReviewActionizer
    -> LayoutReviewCase(LayoutBlockReviewEvidence[])
    -> external human annotation
    -> LayoutAnnotationCollection
```

## Authority

`PageLayoutResult` from the deterministic analyzer remains authoritative.
`LayoutRegionProposal` is unaccepted model or heuristic output.
`LayoutReviewCase` is deterministic comparison and selection evidence.
`LayoutAnnotationCollection` is human-authored benchmark evidence, but does not
accept a proposal, replace `PageLayoutResult`, or authorize publication.

A future acceptance operation must own any authority transition explicitly.
Workflow remains responsible for topology, retries, leases, approvals,
checkpoints, and stop propagation; none of those lifecycle concepts are inferred
by these synchronous actions.

## Semantic ownership

- `layout/render/` owns exact rendered-page identity and source/pixel mapping.
- `layout/proposal/` owns backend-neutral, explicitly unaccepted region
  proposals and proposal-source identity.
- `layout/review/` owns deterministic comparison and review-case preparation.
- `layout/annotation/` owns human corrections, failure labels, and corrected
  reading-order evidence.
- `integrations/layout_parser/` owns LayoutParser resource binding and frozen
  detection adaptation.

Vendor types never enter the layout domain. Package initializers are docstring-only
ownership markers, and consumers import defining leaves directly.

## Complete request

`LayoutReviewRequest` binds:

- one exact authoritative `PageLayoutResult`;
- one exact `LayoutPageRenderEvidence`;
- one backend-neutral `LayoutRegionProposalSource`;
- an ordered tuple of proposals from that source; and
- one immutable `LayoutReviewConfiguration`.

The request validates source, blob, page, coordinate-system, rotation, full-page
bounds, render dimensions, proposal source, proposal render identity, proposal
uniqueness, and implementation limits. It rejects the request before comparison
when block count, proposal count, or their Cartesian product exceeds configured
bounds.

Render evidence is independent of the analyzer result. The request, not the
render, owns their exact relation.

## Per-block normalized evidence

`LayoutBlockReviewEvidence`, defined by `layout/review/block.py`, is the normalized
unit of review output. There is exactly one record for every input text block,
in authoritative block order. It contains:

- block identity;
- its transformed pixel bounding box, or `None` when geometry cannot be mapped;
- status: `covered`, `uncovered`, or `invalid_geometry`;
- all positive proposal overlaps for the block; and
- ordered significant proposal identities.

`LayoutReviewCase` contains the complete request and the ordered block-review
records. Page coverage, reason codes, and `requires_review` derive from those
records. The result does not persist separate global overlap, covered,
uncovered, and invalid-ID collections that could disagree.

Convenience views may expose those partitions as computed properties, but they
are not additional serialized sources of truth.

## Pixel-space overlap

`LayoutBlockRegionOverlap` uses `LayoutPixelMapping`; it never infers scale from
page and image dimensions. The operation:

1. maps all four source-block corners into pixel space;
2. normalizes the exact quarter-turn envelope;
3. intersects that box with one proposal box;
4. records the positive intersection; and
5. computes intersection over mapped block area.

The overlap evidence includes the render mapping identity, block identity,
proposal identity, intersection box, and normalized ratio. Invalid or
out-of-raster native geometry is linked to the block review as invalid geometry
rather than converted into false coverage.

## Bounded algorithm

Review preparation has the explicit cost model:

```text
O(blocks × proposals) + O(overlaps) + O(blocks)
```

The request bounds `blocks × proposals` before work begins. The actionizer then
processes each block once:

1. map block geometry once;
2. scan the proposal tuple once;
3. collect positive and significant overlaps;
4. derive proposal kinds and block status; and
5. emit one `LayoutBlockReviewEvidence`.

No covered block rescans a global overlap collection. Membership checks use
sets or the current block-local evidence, not tuples. The running overlap count
is checked as overlaps are produced.

Review reasons remain deterministic and include baseline ambiguity, baseline
warnings, invalid geometry, no proposals, incomplete coverage, and conflicting
region kinds.

## Result reconstruction and identity

`LayoutReviewCase` retains its complete bounded request so deserialization can
validate:

- exact input block coverage and order;
- proposal and render references;
- block-review status consistency;
- overlap identities and geometry;
- page coverage ratio;
- reason ordering and uniqueness; and
- actionizer/configuration identity.

Stable identities include every persisted field that can change behavior.
Stable identity is integrity evidence, not publication acceptance.

All factories validate and normalize external values before calling
`stable_id()`. `__post_init__` repeats reconstruction checks for direct
construction and deserialization.

## Annotation

Human annotation remains separate from review preparation. Annotation records
may identify corrected regions, native-block membership, observed failures, and
reading-order edges.

`layout/annotation/order.py` owns graph validation. It uses a bounded Kahn
traversal with a deque, rejects self-edges and duplicate endpoint relations, and
checks acyclicity in `O(blocks + edges)`. `LayoutAnnotationCollection`
coordinates validated records; it does not own graph algorithms.

Valid annotation block identities derive from the case's ordered
`LayoutBlockReviewEvidence` records.

## Resource bounds

Bounds are enforced before stable-ID serialization:

- shared identity-field and coordinate bounds in `layout/limits/`;
- raster dimension and pixel-area bounds in `layout/render/limits/`;
- proposal count bounds in `layout/proposal/limits/`;
- block, comparison, and overlap bounds in `layout/review/limits/`; and
- annotation record and edge bounds in `layout/annotation/limits/`.

These contracts do not accept generic metadata or an optional ``evidence``
key/value bag. Detection lineage, resource identity, geometry, affected
annotation identities, and review outcomes use explicit typed fields. A future
operation that consumes human notes or external artifacts must introduce a
bounded operation-specific contract rather than adding arbitrary metadata.
Finite numeric validation also rejects booleans, NaN, infinity, singular
transforms, and invalid boxes.

## Private evidence

Private PDFs, page images, model weights, and annotation images remain outside
the repository. Repository contracts retain hashes, dimensions, coordinate
mapping, stable source identities, bounded geometry, and derivation lineage.
External annotation tools may serialize these immutable contracts using the
canonical ingestion serializer.

## Rejected shortcuts

The architecture explicitly rejects:

- deriving pixel geometry from width/height ratios;
- attaching a loose transform tuple directly to the review request;
- accepting generic metadata or optional key/value evidence bags;
- binding render identity to one analyzer result;
- persisting parallel block partitions that can disagree;
- accepting caller-supplied LayoutParser outputs as an adaptation result;
- lowering count limits to conceal a quadratic algorithm;
- timing-based tests as the only complexity evidence;
- adding LayoutParser, Torch, model weights, or unsafe checkpoint loading to the
  core environment; and
- compatibility aliases or legacy decoders for the unpublished provisional
  contracts.

## Acceptance evidence

Before publication, the implementation must demonstrate:

- exact 0/90/180/270-degree mapping tests;
- translated-origin and outward-rounding mapping tests;
- singular, non-finite, inconsistent-bound, and oversized-render rejection;
- stale, cross-request, omitted, duplicated, and reordered detection/proposal
  lineage rejection;
- one-pass maximum-bound review behavior;
- exact-limit and limit-plus-one scalar/aggregate tests;
- annotation duplicate-edge and cycle rejection;
- stable canonical serialization and replay;
- two byte-identical generations of all six private canary review cases; and
- Ruff, Mypy, focused tests, full tests, Sphinx, smell gates, and clean-wheel
  import validation.
