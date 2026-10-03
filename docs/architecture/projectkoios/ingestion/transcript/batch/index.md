# `projectkoios.ingestion.transcript.batch`

This package owns deterministic transcript-batch contracts, planning,
resolution, execution composition, and immutable publication.

It is a transcript-owned composition boundary. It may select concrete PDF
adapters explicitly, but it does not move adapter execution into the transcript
domain.

## Planned modules

- `contracts.py` — immutable batch items, plans, resolved items, and typed
  errors.
- `planning.py` — bounded plan construction, resolution, serialization, and
  durable plan publication.
- `execution.py` — one-item deterministic composition, derivation audit, and
  immutable output publication.
- `plan_cli.py` and `compose_cli.py` — thin command entry points.
