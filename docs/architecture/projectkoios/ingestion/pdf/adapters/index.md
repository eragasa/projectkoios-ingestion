# `projectkoios.ingestion.pdf.adapters`

This package owns concrete optional-backend integrations for PDF extraction and
rendering. Adapters translate backend-specific documents, pages, dictionaries,
geometry, assets, outlines, and raster mechanics into backend-neutral owner
contracts.

Adapters do not own OCR, semantic reconciliation, reading-order policy,
transcript projection, indexing, or product routing.

## Contents

- [`pymupdf`](pymupdf/index.md) — concrete PyMuPDF extraction and rendering.
