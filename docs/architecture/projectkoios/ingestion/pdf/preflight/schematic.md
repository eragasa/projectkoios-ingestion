# `projectkoios.ingestion.pdf.preflight` schematic

```mermaid
flowchart LR
    Request["source + bounded selections"]
    Measurements["primitive page/raster measurements"]
    Policy["preflight policy"]
    Plan["immutable allocation plan"]
    Adapter["concrete adapter"]

    Request --> Policy
    Measurements --> Policy
    Policy --> Plan
    Plan --> Adapter
```

Only validated primitive facts cross from a concrete adapter into preflight;
backend document, page, rectangle, matrix, pixmap, and colorspace objects do
not.
