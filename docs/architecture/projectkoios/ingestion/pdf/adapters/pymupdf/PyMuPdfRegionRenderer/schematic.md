# `PyMuPdfRegionRenderer` schematic

```mermaid
classDiagram
    class PageRegionRenderer
    class PdfRegionRenderer
    class PdfRegionRenderPreflight
    class PyMuPdfRegionRenderer
    class PyMuPDF
    class RenderedRegion

    PageRegionRenderer <|-- PdfRegionRenderer
    PdfRegionRenderer <|-- PyMuPdfRegionRenderer
    PdfRegionRenderer --> PdfRegionRenderPreflight : composes
    PdfRegionRenderer --> RenderedRegion : creates
    PyMuPdfRegionRenderer --> PyMuPDF : hook implementation
```

The PDF base owns the template workflow and domain result. The concrete adapter
implements only backend lifecycle, geometry, identity, raster, and encoding
hooks.
