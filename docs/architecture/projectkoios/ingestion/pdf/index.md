# `projectkoios.ingestion.pdf`

This package owns PDF-specific ingestion contracts, portable batch records,
backend-neutral extraction actions, extraction artifacts, nominal renderer
bases, and bounded region-render policy.

Concrete dependency loading and backend document/page execution belong under
`pdf.adapters`. The `pdf.extraction` package must not import PyMuPDF or select a
backend. Downstream interpretation of extracted or rendered evidence remains
outside this package.

## Contents

- [`batch`](batch/index.md) — immutable portable PDF batch items and plans.
- [`extraction`](extraction/index.md) — backend-neutral block extraction actions
  and extraction contracts.
- [`adapters`](adapters/index.md) — concrete optional-backend integrations.
- [`renderer`](renderer/index.md) — nominal renderer bases.
- [`preflight`](preflight/index.md) — bounded neutral render policy.
- [`implementation.md`](implementation.md) — ownership and migration plan.
- [`schematic.md`](schematic.md) — package relationships.
