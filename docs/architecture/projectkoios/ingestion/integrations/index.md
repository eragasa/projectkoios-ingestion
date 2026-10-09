# `projectkoios.ingestion.integrations`

Concrete external runtime and persistence integrations. Core ingestion contracts do not depend on provider implementations.

Current integrations:

- [`disk`](disk/index.md) — authoritative extraction recovery and explicitly bound managed-artifact bytes;
- [`mongodb`](mongodb/index.md) — rebuildable operational projections and explicit schema migration;
- [`sqlite`](sqlite/processing/state/index.md) — local durable processing-state checkpoints;
- [`pix2tex`](pix2tex/index.md) — bounded Pix2Tex equation recognition;
- [`ollama`](ollama/index.md) — bounded local Ollama processing;
- [`layout_parser`](layout_parser/index.md) — frozen LayoutParser detection adaptation without an in-process vendor runtime;
- [`coco`](coco/index.md) — framework-neutral COCO-compatible layout-detection interchange and deterministic proposal adaptation; and
- [`docling`](docling/index.md) — pinned rule-based reading-order candidate generation that requires later deterministic verification.

Prototype transcript/page files have no runtime compatibility adapter in the clean rewrite.
