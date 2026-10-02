# `projectkoios.ingestion.pdf.adapters` implementation

The package initially contains only `pymupdf.py`. Its initializer may expose the
concrete adapter within the adapter namespace but contains no behavior. No
abstract adapter base, registry, protocol, factory, compatibility alias, or
wrapper is introduced.

`PyMuPdfRegionRenderer` nominally inherits `PdfRegionRenderer`, which nominally
inherits `PageRegionRenderer`. Only composition roots and integration tests
import or construct the concrete adapter; neutral root packages do not export
it. Every backend-specific import, object, coordinate transformation, raster
geometry calculation, render call, and encoding operation remains inside the
concrete adapter module.
