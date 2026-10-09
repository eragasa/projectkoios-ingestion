# `projectkoios.ingestion.storage.transcript.reading.evidence`

Backend-neutral current-schema persistence projection and reconstruction for canonical reading evidence.

It defines immutable logical records, canonical JSON boundaries, completion evidence, pure projection, a fixed projection/materialization pipeline, strict reconstruction, explicit equivalence verification, and abstract materialization/read ports. Disk, SQLite, and MongoDB integrations may implement those ports without owning canonical storage semantics.

See the [implementation](implementation.md), [schematic](schematic.md), and [structural path map](structural-path-map.md).
