# Article-structure structural path map

This is the reviewed source inventory for the article-structure hierarchy and
shared document-structure analyzer migration. Paths are relative to
`src/python/projectkoios/ingestion`. Removed paths are not retained as aliases
or re-export facades.

| Removed path and owner | Direct owner path |
|---|---|
| `article_structure.py`: processor version | `articles/structure/constants.py` |
| `article_structure.py`: hard ceilings | `articles/structure/limits/definition.py` |
| `article_structure.py`: `ArticleStructureLimitError` | `articles/structure/limits/error.py` |
| `article_structure.py`: `ArticleStructureConfiguration` | `articles/structure/configuration.py` |
| `article_structure.py`: `DeterministicArticleStructureAnalyzer` | `articles/structure/analyzer/deterministic.py` |
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
| `articles/base.py`: `ArticleStructureAnalyzer` | `articles/structure/analyzer/base.py` |
| `textbooks/base.py`: `TextbookStructureAnalyzer` | `textbooks/structure/analyzer/base.py` |

`DocumentStructureAnalyzer` is a new common nominal boundary defined at
`documents/structure/analyzer.py`. The article and textbook boundaries inherit
from it. Their ingester contracts remain domain-specific, while shared
implementations no longer require an article/textbook multiple-inheritance
diamond.

## Semantic review

- Articles own the deterministic article algorithm and its configuration,
  evidence, heading, proposal, validation, and result-derivation concerns.
- The common analyzer contract belongs to `documents/structure/` because its
  signature consumes `ExtractedDocument` and returns `StructureAnalysis`; no
  unsupported `Publication` ontology is introduced.
- Article and textbook analyzers remain nominal domain refinements of that one
  contract. A concrete analyzer chooses one domain boundary rather than
  inheriting both refinements.
- `result/derivation.py` names a pure conversion into structure nodes and
  warnings. It is not an effectful Materializer and performs no publication.
- Hard ceilings and their failure use the plural `limits/` owner.
- Package initializers in migrated scopes are docstring-only ownership markers.
  Consumers import definitions from direct leaves; ingestion, article, and
  textbook package roots do not expose compatibility aliases.
- Processor versions, configuration identity, evidence ordering, proposal
  policy, node and warning identities, analysis identity, field order,
  serialized bytes, and non-acceptance semantics are unchanged.
- Clean-transcript, transcript-batch, Workflow, Pipeline, and operational
  behavior are outside this change.
