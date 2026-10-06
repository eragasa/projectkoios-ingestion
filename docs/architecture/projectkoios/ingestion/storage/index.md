# `projectkoios.ingestion.storage`

This namespace owns backend-neutral durable-storage boundaries:

- [`extraction`](extraction/index.md) publishes exact extraction evidence and
  supports rebuildable projections; and
- [`processing_state`](processing/state/index.md) persists bounded operational
  checkpoints without exposing backend query objects.
