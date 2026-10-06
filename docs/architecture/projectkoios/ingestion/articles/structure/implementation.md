# Article-structure implementation

The nominal analyzer spine is:

```text
DocumentStructureAnalyzer
├── ArticleStructureAnalyzer
│   └── DeterministicArticleStructureAnalyzer
└── TextbookStructureAnalyzer
```

`DocumentStructureAnalyzer` owns the shared synchronous contract from one exact
`ExtractedDocument` to one `StructureAnalysis`. Article and textbook analyzers
remain domain-specific injection boundaries without duplicating the method
contract or requiring concrete implementations to form a multiple-inheritance
diamond.

The deterministic article analyzer consumes exact bounded layout evidence. It
validates document/layout correspondence, derives ordered text evidence,
proposes front matter, sections, bibliography entries, and appendices, applies
matching table-of-contents evidence, establishes proposal hierarchy, and derives
immutable structure nodes and warnings.

Heading recognition, proposal families, evidence records, input validation,
normalization, and result derivation have direct semantic owners under
`articles/structure/`. Result derivation is pure: it neither publishes data nor
implements the effectful Materializer contract.

The analyzer continues to produce proposals rather than accepted semantic
structure. Stable processor/configuration identity, evidence order, bounds,
node identities, warning identities, hierarchy, and serialized analysis bytes
are preserved. Package initializers are docstring-only and provide no
compatibility exports. The complete reviewed inventory is the
[structural path map](structural-path-map.md).
