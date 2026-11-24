# `projectkoios.ingestion.documents.page`

Proposed source-owner contract for a parallel immutable `Page` whose exact
source items are persisted as an ordered keyed `PageItemInventory`.

This records the owner decision that the source Page—not `layout.page`—defines
page-item identity, order, lookup, and inventory identity. It also freezes the
prerequisite split between generic `AbstractDocumentPage` and text-specific
`AbstractTextDocumentPage`; generic Page construction must not invent joined
text. The current `ExtractedPage`, `ExtractedBlock`, and nominal page contracts
remain authoritative until separately reviewed implementation and explicit
cutover.

- [Implementation design](implementation.md)
- [Schematic](schematic.md)
- [Structural path map](structural-path-map.md)
