# `ingestion.figures` schematic

```mermaid
flowchart LR
    Layout["layout evidence"]
    Renderer["PageRegionRenderer"]
    Inspector["figure inspector"]
    Detection["figure detection"]
    Result["figure evidence"]

    Layout --> Detection
    Renderer --> Detection
    Inspector --> Detection
    Detection --> Result
```

Concrete renderer composition stays outside the package's neutral detection
boundary.
