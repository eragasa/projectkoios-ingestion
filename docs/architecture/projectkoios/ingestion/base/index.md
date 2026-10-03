# `projectkoios.ingestion.base`

This module owns the nominal data-object hierarchy shared by ingestion domains.

```text
AbstractDataObject
└── AbstractImmutableDataObject
    └── AbstractIdentity
```

Concrete identity records inherit `AbstractIdentity`. The hierarchy does not
add serialization, mutation, persistence, or external-effect behavior.
