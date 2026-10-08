# `projectkoios.ingestion.integrations.mongodb.transcript.reading.evidence`

Thin MongoDB materialization/source adapter for the backend-neutral current reading-evidence storage contract. It owns physical collection mapping, BSON bounds, create-once writes, bounded reads, and provider errors; canonical projection, JSON, manifests, reconstruction, and equivalence remain under `projectkoios.ingestion.storage.transcript.reading.evidence`.

See the [implementation](implementation.md) and [schematic](schematic.md).
