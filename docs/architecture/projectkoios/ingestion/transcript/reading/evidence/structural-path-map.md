# Reading-evidence structural path map

## Prototype discovery to clean ownership

| Prototype concern | Clean defining owner |
|---|---|
| workflow page composition | `transcript/reading/evidence/projection/actionizer.py::ReadingEvidenceProjectionActionizer` |
| native/OCR page selection | `input/page/evidence.py::ReadingPageTextProducerEvidence` and `input/page/inventory.py` |
| prototype structured role/order | `ReadingStructuredItemProducerEvidenceInventory` joined by the projector |
| prototype clean transcript blocks | `ReadingCleanTextProducerEvidenceInventory` plus `ReadingTextBlockProjectionBasis` |
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
