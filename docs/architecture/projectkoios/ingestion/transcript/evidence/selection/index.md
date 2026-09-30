# `projectkoios.ingestion.transcript.evidence.selection`

**Status:** implemented bounded development vertical for downstream authoring.

This package selects exact `CleanTranscriptBlock.record_id` values from one
canonical [`CleanTranscript`](../../../../../../contracts/clean-transcript.md).
It returns canonically ordered page and block evidence with separate clean
indexed text and exact retained raw text. It does not make source-asset,
reference, rights, use, search, citation, generation, persistence, schema, API,
workflow, or private-data decisions.

## Modules

- [`contracts`](contracts/index.md) — request/result, outcome, and limit error.
- [`evidence`](evidence/index.md) — paired block and page evidence records.
- [`selector`](selector/index.md) — the semantic selection performer.
- [`schematic.md`](schematic.md) — package and action relationships.
- [`implementation.md`](implementation.md) — package export and ownership rules.
