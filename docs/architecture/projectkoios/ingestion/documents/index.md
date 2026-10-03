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

The established `ExtractedArticle` and `ExtractedTextbook` imports remain
available from `projectkoios.ingestion.documents`.
