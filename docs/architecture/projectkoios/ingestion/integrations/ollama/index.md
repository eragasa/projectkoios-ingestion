# `projectkoios.ingestion.integrations.ollama`

This package owns the Ollama integration boundary.

- `base.py` contains shared immutable values, request options, transport
  failures, and the injectable transport abstract base.
- [`transport`](transport/index.md) contains concrete transport adapters.
- [`multimodal`](multimodal/index.md) contains owner-controlled multimodal
  values and its region processor.

Package initializers remain namespace-only. Consumers and implementation code
import each type from its defining integration module.
