# `projectkoios.ingestion.pdf.adapters.pymupdf`

This package owns the core concrete PyMuPDF extraction and rendering
integrations. It owns their lazy dependency loading, backend document/page
mechanics, raw extraction dictionaries, image assets, outline destinations,
coordinate translation, raster execution, and backend-version evidence.
Domain-specific figure and table inspectors retain their existing ownership for
this bounded checkpoint.

## Contents

- [`PyMuPdfExtractor`](PyMuPdfExtractor/index.md) — deterministic cold PDF
  extraction adapter.
- [`PyMuPdfRegionRenderer`](PyMuPdfRegionRenderer/index.md) — bounded region
  rendering adapter.
