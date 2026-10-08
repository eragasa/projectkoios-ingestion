# Reading-evidence structural path map

## Prototype discovery to clean ownership

| Prototype concern | Clean defining owner |
|---|---|
| workflow page composition | `transcript/reading/evidence/projection/actionizer.py::ReadingEvidenceProjectionActionizer` |
| native/OCR page selection | `input/page.py::ReadingPageTextProducerEvidence` and inventory |
| prototype structured role/order | `ReadingStructuredItemProducerEvidenceInventory` joined by the projector |
| prototype clean transcript blocks | `ReadingCleanTextProducerEvidenceInventory` plus `ReadingTextBlockProjectionBasis` |
| workflow-local figure records | `input/figure.py::ReadingFigureProducerEvidence` and inventory |
| workflow-local table records | `input/table.py::ReadingTableProducerEvidence` and inventory |
| workflow-local equation records | `input/equation.py::ReadingEquationProducerEvidence` and inventory |
| raw rendered-member paths | shared `artifact/managed/reference.py::ManagedArtifactReference` |
| ad hoc page dictionaries | `ReadingEvidencePage`, semantic inventories, and `ReadingEvidenceDocument` |
| flat text-only projection | `page/projection` pure action |
| MongoDB persistence | `integrations/mongodb/transcript/reading/evidence` materialization/source/migration |

## Clean break

The prototype Python modules, JSONL layouts, summary fields, validation IDs, and historical report bytes do not define the new API. No alias, decoder, compatibility re-export, report replay contract, legacy profile, or stable-ID preservation is planned.

If prototype data must be retained, it is migrated through the explicit versioned MongoDB migration boundary into the current schema. Runtime domain and page-projection code read only the current canonical schema.
