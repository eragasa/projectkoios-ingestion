# `projectkoios.ingestion.pdf.preflight.policy`

This module owns the single backend-neutral policy path for validating a PDF
region-render request and approving all per-selection and aggregate raster
allocations before rendering. It reports bounded-resource rejection through the
stable render-limit error.
