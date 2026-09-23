# Deterministic Ingestion v0 Implementation

## Components

| Component | Source | Focused validation |
|---|---|---|
| `DeterministicLayoutProcessor` | [`layout.py`](../../../../../src/python/projectkoios/ingestion/layout.py) | [`test__DeterministicLayoutProcessor.py`](../../../../../tests/test__DeterministicLayoutProcessor.py) |
| `DeterministicOCRReconciler` | [`reconciliation.py`](../../../../../src/python/projectkoios/ingestion/reconciliation.py) | [`test__OCRReconciliation.py`](../../../../../tests/test__OCRReconciliation.py) |
| `DeterministicArticleStructureAnalyzer` | [`article_structure.py`](../../../../../src/python/projectkoios/ingestion/article_structure.py) | [`test__ArticleStructureAnalyzer.py`](../../../../../tests/test__ArticleStructureAnalyzer.py) |
| `DeterministicEquationCandidateDetector` | [`equations.py`](../../../../../src/python/projectkoios/ingestion/equations.py) | [`test__EquationCandidateDetector.py`](../../../../../tests/test__EquationCandidateDetector.py) |
| `DeterministicEquationAssembler` | [`equation_enrichment.py`](../../../../../src/python/projectkoios/ingestion/equation_enrichment.py) | [`test__EquationEnrichment.py`](../../../../../tests/test__EquationEnrichment.py) |
| `DeterministicTableCandidateDetector` | [`tables.py`](../../../../../src/python/projectkoios/ingestion/tables.py) | [`test__TableCandidateDetector.py`](../../../../../tests/test__TableCandidateDetector.py) |
| `DeterministicTableStructureReconstructor` | [`table_structure.py`](../../../../../src/python/projectkoios/ingestion/table_structure.py) | [`test__TableStructureReconstructor.py`](../../../../../tests/test__TableStructureReconstructor.py) |
| `DeterministicFigureCandidateDetector` | [`figures.py`](../../../../../src/python/projectkoios/ingestion/figures.py) | [`test__FigureCandidateDetector.py`](../../../../../tests/test__FigureCandidateDetector.py) |
| `DeterministicStructuredTranscriptionComposer` | [`transcription.py`](../../../../../src/python/projectkoios/ingestion/transcription.py) | [`test__StructuredTranscriptionComposer.py`](../../../../../tests/test__StructuredTranscriptionComposer.py) |
| `DeterministicCleanTranscriptProjector` | [`transcript_projection.py`](../../../../../src/python/projectkoios/ingestion/transcript_projection.py) | [`test__CleanTranscriptProjection.py`](../../../../../tests/test__CleanTranscriptProjection.py) |
| `DeterministicCleanTranscriptV2Projector` | [`transcript_v2.py`](../../../../../src/python/projectkoios/ingestion/transcript_v2.py) | [`test__CleanTranscriptV2.py`](../../../../../tests/test__CleanTranscriptV2.py) |
| `DerivationAuditValidator` | [`provenance.py`](../../../../../src/python/projectkoios/ingestion/provenance.py) | [`test__DerivationAuditValidator.py`](../../../../../tests/test__DerivationAuditValidator.py) |

## Public Surface

The component protocols are declared in
[`protocols.py`](../../../../../src/python/projectkoios/ingestion/protocols.py).
Public implementations and models are re-exported from
[`projectkoios.ingestion`](../../../../../src/python/projectkoios/ingestion/__init__.py).

There is not yet an implemented v0 `DeterministicProcessor` composition root.
Iteration two designs `BaseDeterministicProcessor`, `DeterministicProcessor`,
and `PilotDeterministicProcessor` as an ordered composition boundary around a
verified `PdfProcessedDocument`. Until that prefix is implemented and tested,
callers compose the existing components directly or use the existing batch
entry points.

See [architecture.md](architecture.md) for the governing invariants and
[index.md](index.md) for the summary.
