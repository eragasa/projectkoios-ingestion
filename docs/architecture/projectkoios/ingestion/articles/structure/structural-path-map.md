# Article-structure structural path map

This is the reviewed source inventory for the article-structure hierarchy and
action-contract migration. Paths are relative to
`src/python/projectkoios/ingestion`. Removed paths are not retained as aliases
or re-export facades.

| Removed path and owner | Direct owner path |
|---|---|
| `article_structure.py`: processor version | `articles/structure/constants.py` |
| `article_structure.py`: hard ceilings | `articles/structure/limits/definition.py` |
| `article_structure.py`: `ArticleStructureLimitError` | `articles/structure/limits/error.py` |
| `article_structure.py`: `ArticleStructureConfiguration` | `articles/structure/configuration.py` |
| `article_structure.py`: deterministic processor | `articles/structure/actionizer.py` |
| `article_structure.py`: `_TextEvidence` and ordered text evidence | `articles/structure/evidence/text.py` |
| `article_structure.py`: ordered unique source spans | `articles/structure/evidence/span.py` |
| `article_structure.py`: `_Proposal` and `_WarningProposal` | `articles/structure/proposal/model.py` |
| `article_structure.py`: proposal orchestration | `articles/structure/proposal/derivation.py` |
| `article_structure.py`: title, author, abstract, keywords, and front-kind proposals | `articles/structure/proposal/front.py` |
| `article_structure.py`: section and bibliography proposals | `articles/structure/proposal/section.py` |
| `article_structure.py`: table-of-contents and parent ordering | `articles/structure/proposal/order.py` |
| `article_structure.py`: evidence-to-proposal construction | `articles/structure/proposal/factory.py` |
| `article_structure.py`: `_Heading` | `articles/structure/heading/model.py` |
| `article_structure.py`: heading recognition and heading policy definitions | `articles/structure/heading/analysis.py` |
| `article_structure.py`: input relation validation | `articles/structure/validation/input.py` |
| `article_structure.py`: structure-node and warning derivation | `articles/structure/result/derivation.py` |
| `article_structure.py`: text normalization | `articles/structure/normalization/text.py` |
| `articles/structure/analyzer/base.py`: article analyzer ABC | removed; request/actionizer/result roles use `ingestion/base` |
| `articles/structure/analyzer/deterministic.py`: deterministic analyzer | `articles/structure/actionizer.py` |
| new complete immutable action request | `articles/structure/request.py` |

`TextbookStructureAnalyzer` remains a separate, pre-existing textbook boundary;
it is not inherited by or used as the article action contract.

## Semantic review

- Articles own the deterministic algorithm and its configuration, request,
  evidence, heading, proposal, validation, actionizer, and result-derivation
  concerns.
- `ArticleStructureRequest` and `ArticleStructureConfiguration` inherit the
  appropriate Ingestion Base immutable/configurable roles.
- `DeterministicArticleStructureActionizer` inherits the concrete configurable
  Ingestion Base action behavior and exposes only `action(request=...)`.
- `StructureAnalysis` implements the Ingestion Base immutable result role while
  preserving its established fields and serialized bytes.
- The removed analyzer ABC is not replaced with a protocol or compatibility
  facade. Specialized implementations may inherit the concrete deterministic
  actionizer.
- Exact layout evidence enters the request consumed by the structure action; no
  actionizer-held configuration or hidden layout-production path remains.
- `result/derivation.py` names a pure conversion into structure nodes and
  warnings. It is not an effectful Materializer and performs no publication.
- Hard ceilings and their failure use the plural `limits/` owner.
- Package initializers in migrated scopes are docstring-only ownership markers.
  Consumers import definitions from direct leaves.
- Processor versions, configuration identity, evidence ordering, proposal
  policy, node and warning identities, analysis identity, field order,
  serialized bytes, and non-acceptance semantics remain unchanged.
