# `projectkoios.ingestion.integrations.mongodb.transcript.reading.evidence`

Operational MongoDB materialization/source provider for current canonical reading evidence, plus explicit side-by-side schema migration. It writes immutable generation records in bounded create-once batches and publishes a completion manifest last.

See the [implementation](implementation.md) and [schematic](schematic.md).
