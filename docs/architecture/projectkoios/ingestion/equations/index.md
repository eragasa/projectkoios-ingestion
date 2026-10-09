# `projectkoios.ingestion.equations`

This package owns nominal equation representations, exact format-specific image
values, representation provenance links, and deterministic candidate detection.
Detection lives in `equations.detection`; image formats and the closed factory
live under `equations.image`. The COCO formula bridge lives outside the domain
under [`integrations.coco.layout.equation`](../integrations/coco/layout/equation/index.md).
Namespace initializers do not re-export classes.
