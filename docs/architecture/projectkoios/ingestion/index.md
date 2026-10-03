# `projectkoios.ingestion`

This package owns source ingestion and destination-independent document
processing. It exposes stable ingestion contracts while keeping format-neutral
policy separate from optional format/backend integrations. The
[`documents`](documents/index.md) and [`transcripts`](transcripts/index.md)
packages define the nominal document, page, and block hierarchy. Shared
identity roots belong to [`base`](base/index.md). External runtime adapters
belong to [`integrations`](integrations/index.md). The backend-neutral
[`storage`](storage/extraction/index.md) boundary publishes exact extraction
decompositions to authoritative disk records and optional rebuildable read
projections. The [`page_projection`](page_projection/index.md) module validates owner reading
artifacts and exposes immutable citation-aligned text-only pages without
exposing equations or media. This package does not own cross-repository routing,
product policy, Search indexes, or downstream authoring.
