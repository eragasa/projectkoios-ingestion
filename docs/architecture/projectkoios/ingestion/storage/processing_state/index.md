# `projectkoios.ingestion.storage.processing_state`

This package owns the backend-neutral durable checkpoint boundary for bounded
processing queues. Workflows exchange concrete immutable registrations,
snapshots, event drafts, save requests, and save results. They never receive
SQL queries, connections, cursors, rows, or backend-specific transaction
objects.
