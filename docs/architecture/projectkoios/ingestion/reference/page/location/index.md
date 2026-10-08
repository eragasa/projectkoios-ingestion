# `projectkoios.ingestion.reference.page.location`

This package owns bounded page locators and payload-free mechanical matching
results over exact ingestion-owned transcript evidence.

- [`definition`](definition/index.md) owns shared stable version identifiers.
- [`anchor`](anchor/index.md) owns normalized topic-anchor values.
- [`inventory`](inventory/index.md) owns semantic anchor collections.
- [`identity`](identity/index.md) owns field-specific identity grammar and bounded derivation; consuming requests own page-index bounds.
- [`locator`](locator/index.md) owns the immutable locator record.
- [`limitation`](limitation/index.md) owns the closed result limitations.
- [`result`](result/index.md) owns the immutable matching result.
- [`projection`](projection/index.md) creates a locator from exact evidence.
- [`matching`](matching/index.md) matches complete token phrases.
- [`verification`](verification/index.md) verifies reusable page lineage.
- [`limits`](limits/index.md), [`error`](error/index.md), and
  [`status`](status/index.md) own bounds, failures, and status.
- [`structural-path-map`](structural-path-map.md) records the clean break.
