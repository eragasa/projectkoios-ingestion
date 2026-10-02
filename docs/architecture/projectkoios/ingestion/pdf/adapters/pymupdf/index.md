# `projectkoios.ingestion.pdf.adapters.pymupdf`

This module is the concrete optional-backend adapter for rendering explicit PDF
page-region selections to canonical in-memory PNG results. It alone owns
backend loading, document/page lifecycle, coordinate translation, exact raster
geometry, raster execution, and backend evidence.
