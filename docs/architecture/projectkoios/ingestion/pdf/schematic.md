# `projectkoios.ingestion.pdf` schematic

```mermaid
flowchart LR
    Corpus["PDF corpus inventory"]
    BatchItem["pdf.batch.item"]
    BatchPlan["pdf.batch.plan"]
    Command["effectful batch command"]
    Backend["PyMuPDF backend values"]
    Adapter["pdf.adapters.pymupdf<br/>concrete integration"]
    Geometry["pdf.extraction.geometry<br/>typed geometry action"]
    Text["pdf.extraction.text<br/>typed text action"]
    Document["ExtractedDocument"]
    PageBase["PageRegionRenderer"]
    PdfBase["PdfRegionRenderer"]
    Render["PyMuPDF rendering adapter"]
    Region["RenderedRegion"]

    Corpus --> BatchItem --> BatchPlan --> Command
    Command --> Adapter
    Backend --> Adapter
    Adapter --> Geometry
    Adapter --> Text
    Geometry --> Adapter
    Text --> Adapter
    Adapter --> Document
    PageBase --> PdfBase
    PdfBase --> Render
    Backend --> Render
    Render --> Region
```

PDF batch records declare portable checksummed inputs but perform no I/O.
Effectful commands verify those declarations and select concrete adapters.
Neutral extraction actions classify typed bounded evidence. Concrete adapters
alone translate backend objects and execute PyMuPDF operations.
