# `projectkoios.ingestion.page_projection`

Prototype feasibility module for reading-scale page projection. Its Python API, path model, JSONL/report formats, identities, and thresholds are not contracts and receive no compatibility layer.

The clean replacement is [`page.projection`](../page/projection/index.md), which consumes current canonical [`transcript.reading.evidence`](../transcript/reading/evidence/index.md) and managed artifact verification evidence. The prototype module is deleted after consumer migration; no façade replaces it.

Database retention across schema changes is provided only by the explicit MongoDB reading-evidence migration hierarchy.
