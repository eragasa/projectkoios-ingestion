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

An optional pytest integration test accepts one environment-configured
content-addressed processed-reference root plus explicit OCR engine and language
resource paths. It minimally selects the bounded ten pages, verifies only their
source and empty-page text hashes, and executes the public render/OCR composition
twice. Canonical result and aggregate digests are compared in memory; no prior
summary or output artifact is read or written. The test is a downstream usage
example, not a production replay, service, workflow, facade, corpus API, or hard
observational schema.
