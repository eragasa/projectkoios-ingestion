# `projectkoios.ingestion.documents`

This package owns the nominal document hierarchy, concrete extracted document
representations, and the shared document-structure analyzer contract.

## Hierarchy

- `AbstractDocument`
  - `AbstractArticle`
  - `AbstractTextbook`
  - `AbstractTranscript` is defined by `ingestion.transcripts`.
- `AbstractDocumentPage`
- `AbstractDocumentBlock`
- `DocumentStructureAnalyzer`
  - `ArticleStructureAnalyzer`
  - `TextbookStructureAnalyzer`

The established `ExtractedArticle` and `ExtractedTextbook` imports remain
available from `projectkoios.ingestion.documents`.
