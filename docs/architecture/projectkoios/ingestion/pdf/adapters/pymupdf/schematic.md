# `pdf.adapters.pymupdf` schematic

```mermaid
flowchart TD
    Request["source + selections"] --> Policy["neutral preflight request checks"]
    Policy --> Document["open concrete PDF document"]
    Document --> Geometry["crop box + rotation + effective page intersection"]
    Geometry --> RasterFacts["exact integer raster geometry"]
    RasterFacts --> Limits["neutral per-selection and aggregate approval"]
    Limits --> Pixmap["backend rasterization"]
    Pixmap --> Match["exact geometry match"]
    Match --> PNG["PNG bytes"]
    PNG --> Result["RenderedRegion"]
```

No raster allocation occurs until all unique selections have approved plans.
Requested ordering and duplicates are reconstructed from the rendered unique
selection map.
