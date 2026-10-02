# `tables.detection` schematic

```mermaid
flowchart LR
    Context["detector context"]
    Renderer["PageRegionRenderer"]
    Plans["bounded table plans"]
    Results["materialized table evidence"]

    Context --> Plans
    Renderer --> Plans
    Plans --> Results
```

The context's renderer is nominally typed and supplied before detection.
