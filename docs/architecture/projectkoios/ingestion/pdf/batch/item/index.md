# `projectkoios.ingestion.pdf.batch.item`

This module defines `PdfBatchItem`, the immutable portable declaration of one
checksummed PDF source and its relative output target.

It owns item-local invariants. JSON object decoding belongs to the separate
`PdfBatchPlanJsonContract`. The item performs no filesystem
access, hashing, extraction, or publication.

## Contents

- [`implementation.md`](implementation.md) — fields, invariants, and decoding.
- [`schematic.md`](schematic.md) — dependencies and consumers.
