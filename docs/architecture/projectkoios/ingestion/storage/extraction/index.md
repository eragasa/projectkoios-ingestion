# `projectkoios.ingestion.storage.extraction`

This package owns the backend-neutral, create-once publication boundary for one
exact `ExtractionResult`. Requests and results are concrete immutable ingestion
data objects. Storage adapters must not expose database queries, connections,
cursors, or untyped envelopes to workflows.
