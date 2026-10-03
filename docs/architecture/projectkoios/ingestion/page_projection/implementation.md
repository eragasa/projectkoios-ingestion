# `ingestion.page_projection` implementation

`validate_page_projection` receives an explicit path-free
`PageProjectionPlanEntry` plus explicit owner artifact paths. It validates the
source digest, composed baseline, physical and printed page order, citations,
contiguous block order, summary reconciliation, paragraph coverage, safe unique
PNG references, and private no-follow owner artifacts.

Caption exclusion uses exact normalized paragraph equality. A prose reference
to a caption, such as “as shown in Figure 0.3”, is not treated as the caption
block itself. Duplicate exact captions on one page and exact caption paragraphs
remain invalid.

Equation evidence must remain unaccepted, review-required, and ineligible for
chunk text. Equation blocks, recognition proposals, and all media fields are
validated but are omitted by construction from `PageProjectionPage`.
Owner-validated figure captions are emitted exactly once as text blocks with
`style="caption"` at the figure block's original order. Downstream consumers
receive immutable paragraph, heading, and caption text only.

The path-free validation report binds explicit document ID, filename, title,
source digest, transcript digest, summary digest, media-manifest digest,
text-only projection digest, reconciled counts, coverage, contract version, and
validation rules. Runtime filesystem paths do not participate in its identity.

`load_owner_validated_page_projection` requires both an explicit plan entry and
an owner validation-report path. It rejects plan/report mismatches, malformed
report identity, transcript digest or count changes, and semantic projection
changes. An external plan therefore cannot substitute its own metadata for the
owner report. Search policy and persistence remain downstream responsibilities.

Page windows are an iterator concern only. Changing `maximum_pages` changes
grouping but not page values, order, or projection identity.
