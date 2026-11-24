# `projectkoios.ingestion.documents`

This package owns the nominal document hierarchy and concrete extracted document
representations.

## Hierarchy

- `AbstractDocument`
  - `AbstractArticle`
  - `AbstractTextbook`
  - `AbstractTranscript` is defined by `ingestion.transcripts`.
- `AbstractDocumentPage`
- `AbstractDocumentBlock`

Article structure uses the domain-owned Ingestion Base request/actionizer/result
operation. `DocumentStructureAnalyzer` remains only for the pre-existing
textbook analyzer boundary.

The established `ExtractedArticle` and `ExtractedTextbook` imports remain
available from `projectkoios.ingestion.documents`.

A parallel source-owner design for `Page` and its persisted ordered/keyed item
inventory is documented under [`documents.page`](page/index.md). The design
freezes a future generic `AbstractDocumentPage` / text-specific
`AbstractTextDocumentPage` split so Page does not invent canonical text. Current
nominal page, `ExtractedPage`, and `ExtractedBlock` contracts remain authoritative
until separately reviewed implementation and explicit cutover.
