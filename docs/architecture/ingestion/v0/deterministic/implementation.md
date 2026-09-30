# Deterministic Ingestion v0 Implementation

## Components

| Component | Source | Focused validation |
|---|---|---|
| `LayoutAnalysisRequest` → `LayoutAnalysisActionizer` → `LayoutAnalysisResult` | [`layout/actionizer.py`](../../../../../src/python/projectkoios/ingestion/layout/actionizer.py) | [`test__LayoutAnalysisActionizer.py`](../../../../../tests/test__LayoutAnalysisActionizer.py) |
| `DeterministicOCRReconciler` | [`reconciliation.py`](../../../../../src/python/projectkoios/ingestion/reconciliation.py) | [`test__OCRReconciliation.py`](../../../../../tests/test__OCRReconciliation.py) |
| `DeterministicArticleStructureAnalyzer` | [`article_structure.py`](../../../../../src/python/projectkoios/ingestion/article_structure.py) | [`test__ArticleStructureAnalyzer.py`](../../../../../tests/test__ArticleStructureAnalyzer.py) |
| `DeterministicEquationCandidateDetector` | [`equations.py`](../../../../../src/python/projectkoios/ingestion/equations.py) | [`test__EquationCandidateDetector.py`](../../../../../tests/test__EquationCandidateDetector.py) |
| `DeterministicEquationAssembler` | [`equation_enrichment.py`](../../../../../src/python/projectkoios/ingestion/equation_enrichment.py) | [`test__EquationEnrichment.py`](../../../../../tests/test__EquationEnrichment.py) |
| `DeterministicTableCandidateDetector` | [`tables/contracts.py`](../../../../../src/python/projectkoios/ingestion/tables/contracts.py) | [`test__TableCandidateDetector.py`](../../../../../tests/test__TableCandidateDetector.py) |
| `DeterministicTableStructureReconstructor` | [`table_structure.py`](../../../../../src/python/projectkoios/ingestion/table_structure.py) | [`test__TableStructureReconstructor.py`](../../../../../tests/test__TableStructureReconstructor.py) |
| `DeterministicFigureCandidateDetector` | [`figures/contracts.py`](../../../../../src/python/projectkoios/ingestion/figures/contracts.py) | [`test__FigureCandidateDetector.py`](../../../../../tests/test__FigureCandidateDetector.py) |
| `DeterministicStructuredTranscriptionComposer` | [`transcription.py`](../../../../../src/python/projectkoios/ingestion/transcription.py) | [`test__StructuredTranscriptionComposer.py`](../../../../../tests/test__StructuredTranscriptionComposer.py) |
| `DeterministicCleanTranscriptProjector` | [`transcript_projection.py`](../../../../../src/python/projectkoios/ingestion/transcript_projection.py) | [`test__CleanTranscriptProjection.py`](../../../../../tests/test__CleanTranscriptProjection.py) |
| `DeterministicCleanTranscriptV2Projector` | [`transcript_v2.py`](../../../../../src/python/projectkoios/ingestion/transcript_v2.py) | [`test__CleanTranscriptV2.py`](../../../../../tests/test__CleanTranscriptV2.py) |
| `DerivationAuditRequest` → `DerivationAuditActionizer` → `DerivationAuditResult` | [`provenance/audit.py`](../../../../../src/python/projectkoios/ingestion/provenance/audit.py) | [`test__DerivationAuditActionizer.py`](../../../../../tests/test__DerivationAuditActionizer.py) |

The figure and table packages keep stable public imports through small explicit
`__init__.py` facades. Their contracts live in `contracts.py`; `inspection.py`,
`detection.py`, and `validation.py` isolate native PDF inspection,
deterministic candidate materialization, and cross-linked result validation.
Processor identities and contract values are unchanged.

## Public Surface

The component protocols are declared in
[`protocols.py`](../../../../../src/python/projectkoios/ingestion/protocols.py).
New operation APIs are exported from their owning domain packages rather than
added to the broad root facade. Existing root imports remain available for
compatibility during this bounded migration. The figures, layout, provenance,
and tables initializers are small explicit facades; their implementation lives
in named `actionizer.py`, `contracts.py`, and `audit.py` modules.

There is no v0 `DeterministicProcessor` composition root. Callers compose these
components directly or use the existing batch entry points. A future
composition API remains deferred until repeated use establishes the required
boundary.

See [architecture.md](architecture.md) for the governing invariants and
[index.md](index.md) for the summary.
