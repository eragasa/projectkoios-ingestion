# `projectkoios.ingestion.integrations`

Concrete external runtime and persistence integrations. Core ingestion contracts do not depend on provider implementations.

Current integrations:

- [`disk`](disk/index.md) — authoritative content-addressed extraction recovery;
- [`mongodb`](mongodb/index.md) — rebuildable operational projections and explicit schema migration;
- [`sqlite`](sqlite/processing/state/index.md) — local durable processing-state checkpoints;
- [`pix2tex`](pix2tex/index.md) — bounded Pix2Tex equation recognition;
- [`ollama`](ollama/index.md) — bounded local Ollama processing; and
- [`layout_parser`](layout_parser/index.md) — frozen LayoutParser detection adaptation without an in-process vendor runtime.

Prototype transcript/page files have no runtime compatibility adapter in the clean rewrite.
