# `pdf.renderer` implementation

`renderer.py` contains `PageRegionRenderer`, `PdfRegionRenderer`, and
`PdfRegionRenderLimitError`. Both renderer classes are nominal abstract bases.
`PageRegionRenderer` preserves the established narrow public shape: `name` and
`version` identity attributes plus an abstract
`render(source, content, selections)` action.

`PdfRegionRenderer` inherits that base and implements the backend-neutral PDF
template method. It owns immutable `RegionRenderConfiguration`, configuration
identity, exact source/request validation, bounded and first-occurrence
selection handling, requested-order reconstruction, neutral preflight and
aggregate limits, backend-hook orchestration, and final `RenderedRegion`
construction. It remains abstract only because backend mechanics are protected
abstract hooks.

The module imports only standard abstract-base, collection, and typing
interfaces plus backend-neutral ingestion/PDF domain models. The base
constructor resolves `PdfRegionRenderPreflight` after renderer definitions are
loaded, preserving the limit error's ownership without a module-load cycle. The
module has no optional backend import, concrete backend name/version lookup,
dynamically typed backend API, document/page type, coordinate/raster geometry,
colorspace, pixmap, or PNG conversion. A static boundary test enforces this
absence.

There is no renderer protocol or duck-typed alias. Existing duplicate local
`_PageRegionRenderer` protocols are removed. Concrete PDF renderers explicitly
inherit `PdfRegionRenderer`; this module contains no factory, registry, wrapper,
compatibility shim, or concrete default export.
