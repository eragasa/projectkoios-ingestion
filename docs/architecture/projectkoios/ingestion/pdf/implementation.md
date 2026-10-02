# `projectkoios.ingestion.pdf` implementation

`pdf.__init__` preserves the existing public `PdfRegionRenderLimitError` and
`PyMuPdfRegionRenderer` imports by exporting the exact objects from their new
canonical modules. It also exports the canonical neutral `PdfRegionRenderer`
contract. Existing PDF models and extractors retain their ownership.

`pdf/renderer.py` remains, but all concrete behavior is removed. It owns only
the neutral renderer protocol and render-limit error; it is neither a
compatibility implementation shim nor an execution layer. Repository-owned
consumers use this one contract instead of defining duplicate local renderer
protocols, while importing the concrete default from `pdf.adapters.pymupdf`.
