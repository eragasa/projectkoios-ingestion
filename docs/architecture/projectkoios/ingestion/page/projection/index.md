# `projectkoios.ingestion.page.projection`

Implemented backend-neutral pure projection from an exact canonical `ReadingEvidenceSourceResult` to citation-aligned text-only pages. It consumes successful managed-artifact verification evidence and defines no storage provider, alternate decoder, Search policy, or publication authority.

The [`enrichment`](enrichment/index.md) package exposes a separate sanitized,
immutable, one-entry-per-projected-block observation of exact retained text and
provenance. It keeps normalized figure captions explicitly unavailable rather
than inventing a raw/clean pair.

See the [implementation](implementation.md), [schematic](schematic.md), and [structural path map](structural-path-map.md).
