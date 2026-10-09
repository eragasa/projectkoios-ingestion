# Docling integration implementation

## Boundary

`DoclingReadingOrderActionizer` invokes Docling's rule-based
`ReadingOrderPredictor` through an optional, pinned provider. The runtime set is
exactly `docling-slim==2.135.0`, `docling-core==2.101.1`, and `Rtree==1.4.1`
under the `layout-reading-order` package extra. Configuration and provider
identity include all three versions and the `reading_order_rb` algorithm name.
An absent or drifting dependency produces typed unresolved evidence.

The request binds the exact render identity, upstream evidence identity, pixel
dimensions, configured reading direction, and a bounded framework-neutral
inventory of semantic regions. Each region retains its Koios kind, exact
render-space box, stable ID, and contiguous producer source index. Vendor
objects remain inside the concrete provider.

## Candidate semantics

A successful provider call returns only the shared framework-neutral candidate
sequence. The actionizer requires an exact, duplicate-free permutation of the
request elements and emits `LayoutReadingOrderCandidateEvidence` binding the
candidate to the exact request, producer implementation, render, upstream
identity, direction, and ordered element evidence. The result independently
requires the successful provider identity to equal the configured pinned
implementation. Unknown, duplicate, incomplete, mistyped, or over-limit output
fails closed before unbounded output traversal or normalization.
Supported Koios kinds map explicitly to Docling labels. `sidebar` and `other`
are unsupported rather than silently coerced. The pinned predictor supports
left-to-right order only; right-to-left requests remain unresolved.

`CANDIDATE_PRODUCED` does not mean verified or resolved. The result deliberately
reports `requires_verification`. The framework-neutral deterministic verifier
under `layout.reading.order` compares the candidate with exact region
membership and geometry, requires complete native-block permutations, and
rejects ambiguous columns, spanning regions, captions, conflicting mappings,
or incomplete coverage.

## Source-order limitation

The pinned Docling implementation uses contiguous element IDs to preserve some
main-text relationships. The adapter therefore records producer source order
instead of hiding that dependency. The synthetic benchmark demonstrates that
identical two-column geometry supplied in column-major and row-major producer
order yields different candidates. Docling cannot consequently serve as a
semantic oracle or sole deterministic resolver.

This limitation is evidence for the planned verifier: candidate agreement may
support a mechanically provable case, while disagreement or underconstrained
geometry must escalate. The benchmark freezes replay and dependency behavior;
it makes no private-corpus accuracy or quality claim.

## Training

The rule-based predictor is not trainable. This integration adds no training
pipeline, learned reading-order weights, or data-labeling authority. Any future
learned pairwise-precedence model requires a separate resource, invocation,
evaluation, and admission contract.
