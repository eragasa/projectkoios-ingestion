# `projectkoios.ingestion.json`

This package owns reusable bounded JSON mechanics for ingestion records and
external evidence.

It distinguishes typed JSON document boundaries from command-line presentation
and backend transport. Domain packages retain ownership of their field schemas
and record reconstruction; they compose the shared JSON machinery through a
precise `JsonContract[T]` specialization.

## Planned modules

- [`value`](value/index.md) — closed JSON values and immutable-object projection.
- [`limits`](limits/index.md) — mandatory parser/serializer resource bounds.
- [`parser`](parser/index.md) — strict bounded UTF-8 JSON parsing.
- [`serializer`](serializer/index.md) — deterministic configurable JSON text and bytes.
- [`contract`](contract/index.md) — typed record-to-JSON boundary composition.
- [`canonical`](canonical/index.md) — canonical compact JSON for identities and immutable records.
- [`error`](error/index.md) — shared JSON boundary failures.

## Architecture

- [`inventory.md`](inventory.md) — existing JSON families and their classification.
- [`implementation.md`](implementation.md) — ownership, invariants, and migration order.
- [`schematic.md`](schematic.md) — dependency direction.
- [`structural-path-map.md`](structural-path-map.md) — initial exact ownership changes.
