# `projectkoios.ingestion.layout`

This package owns deterministic page-layout evidence, exact rendered-page
coordinate mapping, backend-neutral semantic-region proposals, failure review,
model-authored annotation resolution, and optional terminal human review.

The existing deterministic analyzer remains authoritative. Model proposals are
unaccepted, review cases are deterministic comparison evidence, replicated
model resolutions remain non-authoritative model evidence, and human
annotations remain evidence rather than publication acceptance.

- [`render`](render/index.md) — exact pixel identity and source/pixel mapping.
- [`review`](review/index.md) — bounded proposal comparison and review cases.
- [`reading`](reading/index.md) — framework-neutral candidate evidence,
  conservative deterministic reading-order verification, and pure evaluation
  of already-normalized replicated judgments.
- [`annotation`](annotation/index.md) — strict model-response parsing,
  replicated agreement, human annotation, and optional final human review.
- [`integrations.layout_parser`](../integrations/layout_parser/index.md) — frozen
  vendor detection adaptation outside the layout domain.
- [`integrations.coco.layout`](../integrations/coco/layout/index.md) — pinned,
  framework-neutral COCO box-detection adaptation outside the layout domain.
