# `projectkoios.ingestion.integrations`

This package owns concrete integrations with external runtimes and services.
Core ingestion contracts do not depend on integration implementations.

Current integrations:

- `disk` — private content-addressed extraction payloads and recovery journal;
- `mongodb` — optional rebuildable extraction-decomposition projection;
- [`pix2tex`](pix2tex/index.md) — bounded Pix2Tex equation recognition; and
- [`ollama`](ollama/index.md) — bounded local Ollama processing.
