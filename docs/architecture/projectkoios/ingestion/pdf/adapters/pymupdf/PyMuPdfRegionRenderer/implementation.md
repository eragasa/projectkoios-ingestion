# `PyMuPdfRegionRenderer` implementation

The class nominally inherits `PdfRegionRenderer`, which inherits
`PageRegionRenderer`. It preserves its constructor, `name`, `version`,
`backend_name`, configuration, configuration digest, and public `render`
behavior. Configuration, preflight, and the public render template are inherited;
the class implements only protected PyMuPDF hooks.

Those hooks own lazy dependency loading, PyMuPDF version evidence, document and
page lifecycle mechanics, password/page metadata, CropBox and rotation access,
`Rect`/`Matrix` transformations, `page.rect` clipping, exact integer raster
geometry, pixel-to-source evidence, `get_pixmap`, post-raster geometry matching,
colorspace selection, and PNG conversion. Requested display geometry is
intersected with `page.rect` before exact pixel planning and rasterization, while
the originally requested source geometry remains available to the base's
selection evidence and conservative scale guard.

The class does not own request/source validation, selection bounds or
deduplication, resource-limit policy, aggregate approval, requested-order
reconstruction, or `RenderedRegion` construction. Neutral package roots do not
export or construct it; composition roots and integration tests import it
directly from its adapter module.

The optional pytest integration test accepts one environment-configured
content-addressed processed-reference root plus explicit OCR engine and language
resource paths. It reads bounded deterministic native-extraction
`transcript.json` fields for selection, verifies only the selected source and
empty-page text hashes, and executes the public render/OCR composition twice.
Canonical result and aggregate digests are compared in memory. It reads no prior
OCR replay summary or OCR output and writes no artifact. The test is a
downstream composition example, not a production replay, service, workflow,
facade, corpus API, or hard observational schema.
