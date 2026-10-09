# `projectkoios.ingestion.storage.extraction`

[Implementation](implementation.md) · [Schematic](schematic.md) ·
[Sphinx extraction projection API](../../../../../sphinx/extraction_projection.rst)

This package owns the backend-neutral, create-once publication boundary for one
exact `ExtractionResult` and the pure extraction read-model projection.
`ExtractionPublicationEvidence` plus `ExtractionProjectionConfiguration` enter
`ExtractionProjectionProjector`; `ExtractionReadModel` is its immutable output.
Effectful materialization and query-only inventory reading remain separate
adapter roles. Complete-journal, selected-publication, aggregate replay, and
migration-completion evidence make bounded migration phases independently
verifiable without granting cutover authority. Requests and results are concrete
immutable ingestion data objects. Storage adapters must not expose database
queries, connections, cursors, or untyped envelopes to workflows.
