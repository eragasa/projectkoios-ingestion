# `PdfRegionRenderer` implementation

A `Protocol` declares `name`, `version`, `configuration`, the
`configuration_digest` property, and `render`. The render signature accepts a
`SourceDocument`, `BinaryIO`, and iterable of `PageRegionSelection`; it returns
a tuple of `RenderedRegion`.

The protocol supplies no method bodies, default backend, factory, registration,
preflight delegation, or identity behavior. Concrete adapters satisfy it
structurally. Repository consumers use this canonical type instead of retaining
private copies of the same renderer shape.
