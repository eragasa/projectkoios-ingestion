# Reading-evidence structural path map

## Prototype discovery to clean ownership

| Prototype concern | Clean defining owner |
|---|---|
| workflow page composition | `transcript/reading/evidence/projection/actionizer.py::ReadingEvidenceProjectionActionizer` |
| native/OCR page selection | `input/page/evidence.py::ReadingPageTextProducerEvidence` and `input/page/inventory.py` |
| current structured role/order | `input/structure/production/actionizer.py::ReadingStructuredItemProducerActionizer`, producing `ReadingStructuredItemProducerEvidenceInventory` |
| current clean transcript blocks | `input/text/production/actionizer.py::ReadingCleanTextProducerActionizer`, producing `ReadingCleanTextProducerEvidenceInventory` with exact replayable transformations |
| workflow-local figure records | `input/figure/evidence.py::ReadingFigureProducerEvidence` and `input/figure/inventory.py` |
| workflow-local table records | `input/table/evidence.py::ReadingTableProducerEvidence` and `input/table/inventory.py` |
| workflow-local equation records | `input/equation/evidence.py::ReadingEquationProducerEvidence` and `input/equation/inventory.py` |
| raw rendered-member paths | shared `artifact/managed/reference.py::ManagedArtifactReference` |
| ad hoc page dictionaries | `ReadingEvidencePage`, semantic inventories, and `ReadingEvidenceDocument` |
| flat text-only projection | `page/projection` pure action |
| MongoDB persistence | `integrations/mongodb/transcript/reading/evidence` materialization/source/migration |

## Foundational defining leaves

| Semantic owner | Defining leaf |
|---|---|
| typed reading identity and role | `identity/definition.py::ReadingEvidenceIdentity` and `identity/kind.py::ReadingEvidenceIdentityKind` |
| bounded identity derivation | `identity/derivation.py::ReadingEvidenceIdentityDerivation` |
| normalized source geometry | `span/geometry.py::ReadingBoundingBox` |
| exact source span and declared order | `span/evidence.py::ReadingSourceSpanEvidence` and `span/inventory.py` |
| exact native/OCR stream evidence | `stream/evidence.py::ReadingTextStreamEvidence` and `stream/inventory.py` |
| exact selected stream lineage | `stream/selection/definition.py::ReadingTextSelection` and `stream/selection/basis.py::ReadingTextSelectionBasis` |
| clean-text transformations | `input/text/transformation/kind.py`, `input/text/transformation/definition.py`, `input/text/transformation/inventory.py`, `input/text/evidence.py`, and `input/text/inventory.py` |
| shared visual/equation producer lineage | `input/producer/lineage.py::ReadingProducerLineage` |
| shared figure/table assessment | `input/visual/assessment.py::ReadingVisualAssessment` |
| reading domain and limit failures | `error.py::ReadingEvidenceError` and `limits/error.py::ReadingEvidenceLimitError` |

## Current producer defining leaves

| Semantic owner | Defining leaf |
|---|---|
| structured-item production request | `input/structure/production/request.py::ReadingStructuredItemProductionRequest` |
| current structured-item producer action | `input/structure/production/actionizer.py::ReadingStructuredItemProducerActionizer` |
| structured-item production result | `input/structure/production/result.py::ReadingStructuredItemProductionResult` |
| clean-text production request | `input/text/production/request.py::ReadingCleanTextProductionRequest` |
| current clean-text producer action | `input/text/production/actionizer.py::ReadingCleanTextProducerActionizer` |
| exact current transformation replay | `input/text/production/transformation.py::derive_reading_clean_text_transformations` |
| clean-text production result | `input/text/production/result.py::ReadingCleanTextProductionResult` |

These are new current producer boundaries; no production source path was moved or preserved as a compatibility façade.

## Canonical projection defining leaves

| Semantic owner | Defining leaf |
|---|---|
| ordered block vocabulary | `block/kind.py::ReadingEvidenceBlockKind` |
| exact paragraph/heading derivation | `block/text/evidence.py::ReadingTextEvidenceBlock`, `block/text/source.py::ReadingTextBlockSourceInventory`, and `block/text/projection.py` |
| ordered visual/equation blocks | `block/figure/evidence.py`, `block/figure/projection.py`, `block/table/evidence.py`, `block/table/projection.py`, `block/equation/evidence.py`, and `block/equation/projection.py` |
| heterogeneous page block order | `block/inventory.py::ReadingEvidenceBlockInventory` |
| unique caption selection | `caption/evidence.py::ReadingCaptionEvidence`, `caption/basis.py`, and `caption/selection.py` |
| complete canonical pages | `page/evidence.py::ReadingEvidencePage`, `page/inventory.py`, and `projection/page.py::ReadingEvidencePageProjection` |
| exact aggregate lineage | `lineage/definition.py::ReadingEvidenceLineage` |
| typed limitations | `limitation/code.py`, `limitation/affected.py`, `limitation/definition.py`, and `limitation/inventory.py` |
| canonical document aggregate | `document/definition.py::ReadingEvidenceDocument` and `document/validation.py::validate_reading_evidence_document_components` |
| expected and observed inventories | `inventory/measures.py`, `inventory/expected.py`, and `inventory/definition.py` |
| exact reconciliation | `reconciliation/field.py`, `reconciliation/mismatch.py`, and `reconciliation/definition.py` |
| immutable action contract | `projection/request.py`, `projection/validation.py`, `projection/actionizer.py`, and `projection/result.py` |
| limitation derivation | `projection/limitation.py::derive_reading_evidence_limitations` |
| hierarchical projection identities | `projection/identity.py::ReadingEvidenceProjectionIdentityDerivation` |

## Projector implementation reduction

| Previous implementation owner | Reduced semantic owner |
|---|---|
| `document/definition.py::ReadingEvidenceDocument.__post_init__` cross-component validation | `document/validation.py::validate_reading_evidence_document_components` |

## Planned documentation path corrections

| Previous planned documentation path | Implemented defining-leaf documentation path |
|---|---|
| `block/text/ReadingTextEvidenceBlock/` | `block/text/evidence/ReadingTextEvidenceBlock/` |
| `block/figure/ReadingFigureEvidenceBlock/` | `block/figure/evidence/ReadingFigureEvidenceBlock/` |
| `block/table/ReadingTableEvidenceBlock/` | `block/table/evidence/ReadingTableEvidenceBlock/` |
| `block/equation/ReadingEquationEvidenceBlock/` | `block/equation/evidence/ReadingEquationEvidenceBlock/` |
| `caption/ReadingCaptionEvidence/` | `caption/evidence/ReadingCaptionEvidence/` |
| `document/ReadingEvidenceDocument/` | `document/definition/ReadingEvidenceDocument/` |
| `page/evidence/ReadingEvidencePageInventory/` | `page/inventory/ReadingEvidencePageInventory/` |
| `inventory/ReadingEvidenceInventory/` | `inventory/definition/ReadingEvidenceInventory/` |
| `limitation/ReadingEvidenceLimitation/` | `limitation/definition/ReadingEvidenceLimitation/` |
| `limitation/ReadingEvidenceLimitationInventory/` | `limitation/inventory/ReadingEvidenceLimitationInventory/` |
| `lineage/ReadingEvidenceLineage/` | `lineage/definition/ReadingEvidenceLineage/` |
| `reconciliation/ReadingEvidenceReconciliation/` | `reconciliation/definition/ReadingEvidenceReconciliation/` |

These are documentation-path corrections from an unimplemented plan, not compatibility moves. No production source path existed at the old locations.

## Producer contract corrections required by projection

| Previous current-producer representation | Correct defining owner |
|---|---|
| identity-sorted structured source-block membership | `input/structure/source.py::ReadingSourceBlockIdentityInventory`, preserving producer order |
| clean text without source spans | `input/text/evidence.py::ReadingCleanTextProducerEvidence`, with normalized spans and linked geometry warnings |
| clean production request without exact transcription geometry | `input/text/production/request.py::ReadingCleanTextProductionRequest`, binding the exact `StructuredTranscriptionResult` |

## Producer test-support path map

| Previous test-owned path | Current semantic owner |
|---|---|
| `tests/test__CleanTranscript.py::_pdf` | `tests/clean_transcript_support.py::CleanTranscriptSourceFixture.pdf_bytes` |
| `tests/test__CleanTranscript.py::_pipeline` | `tests/clean_transcript_support.py::CleanTranscriptSourceFixture.build` |

## Foundation reduction path map

| Previous committed path | Reduced defining leaf or disposition |
|---|---|
| `input/page.py` | `input/page/evidence.py`; `input/page/inventory.py` |
| `input/structure.py` | `input/structure/kind.py`; `input/structure/evidence.py`; `input/structure/inventory.py` |
| `input/text.py` | `input/text/transformation/kind.py`; `input/text/transformation/definition.py`; `input/text/transformation/inventory.py`; `input/text/evidence.py`; `input/text/inventory.py` |
| `input/figure.py` | `input/figure/evidence.py`; `input/figure/inventory.py`; common lineage and assessment leaves |
| `input/table.py` | `input/table/evidence.py`; `input/table/inventory.py`; common lineage and assessment leaves |
| `input/equation.py` | `input/equation/evidence.py`; `input/equation/inventory.py`; common lineage leaf |
| `span/model.py` | `span/geometry.py`; `span/evidence.py`; `span/inventory.py` |
| `identity/model.py` | `identity/definition.py` |
| `stream/basis.py` | `stream/selection/basis.py` |
| `stream/selection.py` | `stream/selection/definition.py` |
| `stream/evidence.py::ReadingTextStreamEvidenceInventory` | `stream/inventory.py` |
| `association/evidence.py::ReadingAssociationEvidenceInventory` | `association/inventory.py` |
| `artifact/managed/reference.py::ManagedArtifactReferenceInventory` | `artifact/managed/inventory.py` |

All replacement package initializers are docstring-only ownership markers. Consumers import defining leaves directly; no compatibility façade remains.

## Clean break

The prototype Python modules, JSONL layouts, summary fields, validation IDs, and historical report bytes do not define the new API. No alias, decoder, compatibility re-export, report replay contract, legacy profile, or stable-ID preservation is planned.

If prototype data must be retained, it is migrated through the explicit versioned MongoDB migration boundary into the current schema. Runtime domain and page-projection code read only the current canonical schema.
