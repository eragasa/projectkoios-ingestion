# `PyMuPdfRegionRenderer` implementation

The class preserves its constructor, `name`, `version`, `backend_name`,
`configuration`, `configuration_digest`, and `render` behavior. Construction
creates one `RegionRenderConfiguration` and composes one
`PdfRegionRenderPreflight` over it.

`render` validates and bounds selections before optional dependency loading,
validates exact bytes before document parsing, preflights every unique raster
before any `get_pixmap` call, and closes the document on every exit. Concrete
geometry helpers remain private to the adapter. In particular, requested
display geometry is intersected with `page.rect` before exact integer pixel
geometry, limit approval, clipping, and post-render dimension/origin matching.
The originally requested source geometry remains in selection identity and the
conservative scale guard.

Results preserve requested order and return the same object for duplicate
selections. Processor/backend identities and PNG construction remain unchanged,
so the ownership move itself does not authorize output or identity drift.

An optional pytest integration test, configured only through explicit
environment values, deterministically rediscovers and replays the private
bounded ten-page OCR selection twice. It commits no private fixture and writes
no output artifact.
