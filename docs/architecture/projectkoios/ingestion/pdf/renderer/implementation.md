# `pdf.renderer` implementation

`renderer.py` contains only `PdfRegionRenderer`, a typing protocol, and
`PdfRegionRenderLimitError`, a marker `ValueError`. The protocol expresses the
existing stable renderer surface: `name`, `version`, immutable configuration,
configuration digest, and `render(source, content, selections)` returning an
ordered tuple of `RenderedRegion` values.

The module imports only standard typing/collection interfaces and
backend-neutral ingestion/PDF domain models. It has no optional backend import,
backend name/version lookup, `Any` backend objects, preflight implementation,
document/page object, coordinate/raster geometry, colorspace, pixmap, or PNG
conversion. A static boundary test enforces this absence.

This is the sole renderer protocol. Existing duplicate local
`_PageRegionRenderer` protocols are replaced by it rather than layered beneath
it. Concrete defaults remain imported from their adapter modules, so this
module contains no compatibility implementation shim.
