# `projectkoios.ingestion.pdf.renderer`

This module owns the backend-neutral public contract for bounded PDF region
rendering and its stable resource-limit error. It defines required behavior and
evidence shape only; it performs no preflight policy, backend adaptation,
coordinate calculation, document access, rasterization, or encoding.
