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
