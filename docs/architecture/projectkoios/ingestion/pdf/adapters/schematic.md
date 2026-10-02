# `projectkoios.ingestion.pdf.adapters` schematic

```mermaid
flowchart LR
    PageBase["PageRegionRenderer"]
    PdfBase["PdfRegionRenderer"]
    Root["composition root or integration test"]
    Backend["optional PDF backend"]
    Adapter["concrete adapter"]
    Preflight["neutral preflight policy"]
    Result["RenderedRegion"]

    PageBase --> PdfBase
    PdfBase --> Adapter
    Root --> Adapter
    Backend --> Adapter
    Adapter --> Preflight
    Preflight --> Adapter
    Adapter --> Result
```

Composition roots choose concrete adapters. Adapters own backend translation
and execution while the nominal bases and preflight retain neutral contracts
and policy.
