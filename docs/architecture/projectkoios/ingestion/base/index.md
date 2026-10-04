# `projectkoios.ingestion.base`

[Implementation](implementation.md) ·
[LLM harness design](llm-harness-design.md) · [Schematic](schematic.md)

This module owns the nominal data-object hierarchy shared by ingestion domains.

```text
AbstractDataObject
└── AbstractImmutableDataObject
    ├── AbstractIdentity
    ├── AbstractDerivation
    └── AbstractValidation
```

Concrete identity, derivation, and validation records inherit their matching
nominal base. The hierarchy does not add serialization, mutation, persistence,
or external-effect behavior.
