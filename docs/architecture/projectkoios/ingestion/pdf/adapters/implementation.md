# `projectkoios.ingestion.pdf.adapters` implementation

The package initially contains only `pymupdf.py`. Its initializer may export
the concrete renderer class but contains no behavior. No abstract adapter base,
registry, adapter protocol, or compatibility wrapper is introduced. The
concrete class satisfies the single neutral renderer contract owned by
`pdf.renderer`.

Every backend-specific import, type/object, coordinate transformation, raster
geometry calculation, render call, and encoding operation remains inside the
concrete adapter module.
