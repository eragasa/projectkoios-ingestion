# `projectkoios.ingestion.pdf.renderer`

This module owns the nominal backend-neutral bases for page-region rendering and
bounded PDF rendering, plus the stable PDF render-limit error. It defines
identity, action, configuration, and neutral preflight composition boundaries;
it performs no backend adaptation, coordinate calculation, document access,
rasterization, or encoding.
