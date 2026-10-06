# Article-structure implementation

The synchronous operation follows the Ingestion Base action roles:

```text
ArticleStructureRequest
    → DeterministicArticleStructureActionizer
    → StructureAnalysis
```

`ArticleStructureConfiguration` implements the Ingestion-owned action
configuration contract. `ArticleStructureRequest` is a frozen configurable
request that binds one exact `ExtractedDocument`, one ordered layout result per
page, and all deterministic bounds. `StructureAnalysis` is the frozen action
result and retains its established analysis identity and serialized shape.

The actionizer inherits the concrete configurable action behavior from
`projectkoios.ingestion.base.actionizer.configurable`. It has no analyzer ABC,
no protocol boundary, no constructor-held configuration, and no alternate
`analyze` or `analyze_with_layout` route. Specialized implementations may
inherit the concrete deterministic actionizer while preserving the same request
and result roles.

The deterministic action consumes exact bounded layout evidence, validates its
document/page correspondence, derives ordered text evidence, proposes front
matter, sections, bibliography entries, and appendices, applies matching
table-of-contents evidence, establishes proposal hierarchy, and derives
immutable structure nodes and warnings.

Heading recognition, proposal families, evidence records, input validation,
normalization, and result derivation have direct semantic owners under
`articles/structure/`. Result derivation is pure: it neither publishes data nor
implements the effectful Materializer contract.

The action continues to produce proposals rather than accepted semantic
structure. Stable processor/configuration identity, evidence order, bounds,
node identities, warning identities, hierarchy, and serialized analysis bytes
are preserved. Package initializers are docstring-only and provide no
compatibility exports. The complete reviewed inventory is the
[structural path map](structural-path-map.md).
