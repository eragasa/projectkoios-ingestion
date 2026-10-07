# `projectkoios.ingestion.pdf.batch`

This package owns the immutable, portable input records that describe a bounded
batch of PDF source files and the PDF-specific JSON schema that reconstructs
them.

It does not discover files, read source bytes, execute extraction, publish
artifacts, or own Workflow lifecycle. Those effects remain with corpus,
command, extraction, and publication owners.

## Planned modules

- [`item`](item/index.md) — one checksummed PDF source and its portable
  source/output paths.
- [`plan`](plan/index.md) — one ordered, bounded collection of unique PDF batch
  items.
- [`json`](json/index.md) — exact version-1 PDF batch JSON schema and replay.
- [`limits`](limits/index.md) — item-count, bounded-text, and typed limit
  failures.
- `implementation.md` — ownership, invariants, and migration sequence.
- `schematic.md` — package and consumer relationships.
- `structural-path-map.md` — exact source and test path changes.
