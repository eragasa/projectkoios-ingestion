# `projectkoios.ingestion`

This package owns source ingestion and destination-independent document
processing. The touched source-mirrored slice adds a bounded clean-transcript
evidence selection handoff for downstream authoring.

The existing [canonical clean-transcript contract](../../../contracts/clean-transcript.md)
remains authoritative for transcript production and evidence retention; it is
linked rather than duplicated here.

## Contents

- [`transcript`](transcript/index.md) — transcript-owned derivations,
  including exact evidence selection with fail-closed warning handling.
- [`schematic.md`](schematic.md) — touched package relationships.
- [`implementation.md`](implementation.md) — package export and boundary rules.
