# `projectkoios.ingestion.base`

[Implementation](implementation.md) ·
[LLM harness design](llm-harness-design.md) · [Schematic](schematic.md) ·
[Sphinx projector API](../../../../sphinx/projector.rst)

This package owns the nominal data-object hierarchy shared by ingestion domains
and the Ingestion-local pure-projector framework pilot.

```text
AbstractDataObject
└── AbstractImmutableDataObject
    ├── AbstractIdentity
    ├── AbstractDerivation
    └── AbstractValidation

Projector
├── ProjectionRequest[ProjectionSource, ProjectionConfiguration]
└── ProjectionResult[ProjectionValue]
```

Concrete identity, derivation, and validation records inherit their matching
nominal base. Concrete projectors follow the fixed stateless, authority-free,
external-effect-free request-to-result pattern. The hierarchy does not add
serialization, mutation, persistence, or external-effect behavior.
