# Deterministic Ingestion v0 Implementation

## Object-model dependency

The action-family ABCs are supplied by `projectkoios` Git commit
`233f36900b9b44c943ecc5e27f2968ad4bee97ad`, exact tree
`b7c3ffd23086e7ef184c990267d48a56dd87282b`. The declared package source pins
that commit; it never depends on a machine-local repository path.

## Components

| Component | Source | Focused validation |
|---|---|---|
| `LayoutAnalysisRequest` → `DeterministicLayoutProcessor` → `LayoutAnalysisResult` | [`layout/actionizer.py`](../../../../../src/python/projectkoios/ingestion/layout/actionizer.py) | [`test__DeterministicLayoutProcessor.py`](../../../../../tests/test__DeterministicLayoutProcessor.py) |
| `OCRReconciliationRequest` → `DeterministicOCRReconciler` → `OCRReconciliationResult` | [`reconciliation/reconciler.py`](../../../../../src/python/projectkoios/ingestion/reconciliation/reconciler.py) | [`test__DeterministicOCRReconciler.py`](../../../../../tests/projectkoios/ingestion/reconciliation/test__DeterministicOCRReconciler.py) |
| `DeterministicArticleStructureAnalyzer` | [`article_structure.py`](../../../../../src/python/projectkoios/ingestion/article_structure.py) | [`test__ArticleStructureAnalyzer.py`](../../../../../tests/test__ArticleStructureAnalyzer.py) |
| `DeterministicEquationCandidateDetector` | [`equations/detection.py`](../../../../../src/python/projectkoios/ingestion/equations/detection.py) | [`test__EquationCandidateDetector.py`](../../../../../tests/test__EquationCandidateDetector.py) |
| `DeterministicEquationAssembler` | [`equations/assembly/assembler.py`](../../../../../src/python/projectkoios/ingestion/equations/assembly/assembler.py) | [`test__EquationEnrichment.py`](../../../../../tests/test__EquationEnrichment.py) |
| `DeterministicTableCandidateDetector` | [`tables/contracts.py`](../../../../../src/python/projectkoios/ingestion/tables/contracts.py) | [`test__TableCandidateDetector.py`](../../../../../tests/test__TableCandidateDetector.py) |
| `TableStructureRequest` → `DeterministicTableStructureReconstructor` → `TableStructureResult` | [`tables/structure/reconstructor.py`](../../../../../src/python/projectkoios/ingestion/tables/structure/reconstructor.py) | [`test__DeterministicTableStructureReconstructor.py`](../../../../../tests/projectkoios/ingestion/tables/structure/test__DeterministicTableStructureReconstructor.py) |
| `DeterministicFigureCandidateDetector` | [`figures/contracts.py`](../../../../../src/python/projectkoios/ingestion/figures/contracts.py) | [`test__FigureCandidateDetector.py`](../../../../../tests/test__FigureCandidateDetector.py) |
| `DeterministicStructuredTranscriptionComposer` | [`transcription.py`](../../../../../src/python/projectkoios/ingestion/transcription.py) | [`test__StructuredTranscriptionComposer.py`](../../../../../tests/test__StructuredTranscriptionComposer.py) |
| `CleanTranscriptRequest` → `DeterministicCleanTranscriptProjector` → `CleanTranscript` | [`clean_transcript.py`](../../../../../src/python/projectkoios/ingestion/clean_transcript.py) | [`test__CleanTranscript.py`](../../../../../tests/test__CleanTranscript.py) |
| `DerivationAuditRequest` → `DerivationAuditValidator` → `DerivationAuditResult` | [`provenance/audit.py`](../../../../../src/python/projectkoios/ingestion/provenance/audit.py) | [`test__DerivationAuditValidator.py`](../../../../../tests/test__DerivationAuditValidator.py) |

The figure and table-detection packages keep stable public imports through
small explicit `__init__.py` facades. Table-structure consumers import concrete
classes from their owning modules under `tables/structure/`; its initializer is
a namespace marker and no compatibility facade is retained. Table-detection
contracts live in `contracts.py`; `inspection.py`, `detection.py`, and
`validation.py` isolate native PDF inspection, deterministic candidate
materialization, and cross-linked result validation. Processor identities and
contract values are unchanged.

## Public Surface

The component protocols are declared in
[`protocols.py`](../../../../../src/python/projectkoios/ingestion/protocols.py).
New operation APIs are imported from their owning modules rather than added to
the broad root facade. Existing figure, layout, provenance, and table-detection
root imports remain available where their migrations retain compatibility;
table-structure root imports were intentionally removed in favor of direct
owner-module imports. The figures, layout, provenance, and table-detection
initializers remain small explicit facades; their implementation lives in named
`actionizer.py`, `contracts.py`, and `audit.py` modules.

There is no v0 `DeterministicProcessor` composition root. Callers compose these
components directly or use the existing batch entry points. A future
composition API remains deferred until repeated use establishes the required
boundary.

See [architecture.md](architecture.md) for the governing invariants and
[index.md](index.md) for the summary.
