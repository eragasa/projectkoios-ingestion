# `projectkoios.ingestion.pdf` implementation

`pdf.__init__` exports the exact canonical `PageRegionRenderer`,
`PdfRegionRenderer`, and `PdfRegionRenderLimitError` objects from
`pdf.renderer`. It does not export a concrete renderer. Existing PDF models and
extractors retain their ownership.

`pdf/renderer.py` owns the nominal renderer inheritance boundary and neutral PDF
configuration/preflight composition; it is neither a compatibility shim nor an
execution layer. Broad consumers depend on `PageRegionRenderer`, PDF-aware
consumers may depend on `PdfRegionRenderer`, and composition roots import the
concrete default directly from `pdf.adapters.pymupdf`.
