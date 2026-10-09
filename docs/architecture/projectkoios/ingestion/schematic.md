# `projectkoios.ingestion` schematic

```mermaid
flowchart LR
    Source["source documents"]
    PdfExtraction["pdf.extraction<br/>neutral actions"]
    PdfAdapter["pdf.adapters.pymupdf<br/>concrete integration"]
    TranscriptBatch["transcript.batch<br/>composition root"]
    ReadingEvidence["transcript.reading.evidence<br/>canonical reading evidence"]
    ArtifactVerification["artifact.managed.verification<br/>payload-free verified references"]
    PageProjection["page.projection<br/>pure citation-aligned text pages"]
    Search["Search-owned<br/>chunking and retrieval admission"]
    Json["ingestion.json<br/>bounded typed JSON"]
    Owners["layout/equation/table/figure/transcript owners"]
    Outputs["validated derived artifacts"]

    Source --> PdfAdapter
    PdfAdapter <--> PdfExtraction
    PdfAdapter --> TranscriptBatch
    Owners --> TranscriptBatch
    Owners --> Json
    Json --> Outputs
    TranscriptBatch --> ReadingEvidence
    ReadingEvidence --> PageProjection
    ArtifactVerification --> PageProjection
    PageProjection --> Search
    ReadingEvidence --> Outputs
```

Backend integration, neutral actions, canonical reading evidence, managed-artifact verification, pure page projection, JSON document boundaries, and Search-owned retrieval remain distinct ownership boundaries.
