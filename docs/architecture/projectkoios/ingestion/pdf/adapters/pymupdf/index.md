# `projectkoios.ingestion.pdf.adapters.pymupdf`

This module owns the concrete PyMuPDF hook implementation required by the
backend-neutral PDF render template. It alone owns dependency loading,
document/page mechanics, coordinate translation, exact raster geometry,
raster execution, encoding, and backend evidence.
