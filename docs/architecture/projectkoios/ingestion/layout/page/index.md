# `projectkoios.ingestion.layout.page`

Proposed owner-native page-layout contract based on two exact, persisted item
maps:

- the source `Page` owns its ordered page-item map; and
- `PageLayout` owns an ordered `ItemLayout` map with the exact same keys and
  source order.

This is a parallel-build design candidate, not a `v2` rename. It does not
replace the currently authoritative `PageLayoutResult`, change persisted
identities, or authorize a compatibility alias, cutover, publication, or
release. The candidate remains non-authoritative until an explicit cutover
decision after replay and consumer-adoption evidence.

- [Implementation design](implementation.md)
- [Schematic](schematic.md)
- [Structural path map](structural-path-map.md)
