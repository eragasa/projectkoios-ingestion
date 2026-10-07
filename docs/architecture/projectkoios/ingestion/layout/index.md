# `projectkoios.ingestion.layout`

This package owns deterministic page-layout evidence, exact rendered-page
coordinate mapping, backend-neutral semantic-region proposals, failure review,
and human annotation.

The existing deterministic analyzer remains authoritative. Model proposals are
unaccepted, review cases are deterministic comparison evidence, and human
annotations are benchmark evidence rather than publication acceptance.

- [`render`](render/index.md) — exact pixel identity and source/pixel mapping.
- [`review`](review/index.md) — bounded proposal comparison and review cases.
- [`integrations.layout_parser`](../integrations/layout_parser/index.md) — frozen
  vendor detection adaptation outside the layout domain.
