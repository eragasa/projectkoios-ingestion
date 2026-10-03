# `integrations.ollama.multimodal`

This package owns Ollama-specific multimodal values and bounded region
processing. Contract authority remains on each concrete owner; there is no
aggregate multimodal contract class.

- `base.py` defines shared immutable multimodal values. Each value validates
  its own fields.
- `selection/identity.py` owns the versioned selection identity.
- `cache/identity.py` owns the versioned cache-key identity.
- `processor/region/base.py` owns transport orchestration, bounded response
  parsing, and response-schema enforcement.
- `processor/region/identity.py`, `request.py`, and `result.py` own their exact
  class-level contract names and versions.
- `processor/region/preflight/result.py` returns the preflight operation as a
  named result object rather than an anonymous multi-value tuple.
- `processor/region/model_list/result.py` does the same for model-list
  verification.

Released identity namespaces remain stable. A class-level contract version is
part of every stable-ID calculation, while serialized result records retain
their contract version explicitly. Shape changes require a new owner version;
they must not silently reinterpret an older durable record.
