# `projectkoios.ingestion.pdf.adapters`

This package owns concrete integrations that execute PDF operations through
optional third-party backends. Each adapter translates backend-specific page
and raster facts into the neutral preflight boundary and returns canonical PDF
result models; it does not redefine validation or resource policy.
