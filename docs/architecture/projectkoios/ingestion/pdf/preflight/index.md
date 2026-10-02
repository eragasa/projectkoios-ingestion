# `projectkoios.ingestion.pdf.preflight`

This package owns backend-neutral, immutable PDF region-render preflight plans
and the validation/resource-limit policy that creates them. It accepts domain
models and primitive measurements; it never opens documents, imports a raster
backend, or performs coordinate conversion or rendering.
