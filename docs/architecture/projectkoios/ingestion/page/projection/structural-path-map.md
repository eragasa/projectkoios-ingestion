# `projectkoios.ingestion.page.projection` structural path map

## Implemented defining leaves

| Semantic owner | Defining source path |
|---|---|
| `PageProjectionActionizer` | `src/python/projectkoios/ingestion/page/projection/actionizer.py` |
| `PageProjectionTextBlockStyle`, `PageProjectionTextBlock`, `PageProjectionTextBlockInventory` | `src/python/projectkoios/ingestion/page/projection/block.py` |
| `PageProjectionError` | `src/python/projectkoios/ingestion/page/projection/error.py` |
| `PageProjectionInputIdentityDerivation`, `PageProjectionResultIdentityDerivation` | `src/python/projectkoios/ingestion/page/projection/identity.py` |
| `PageProjectionLimitation`, `PageProjectionLimitationInventory` | `src/python/projectkoios/ingestion/page/projection/limitation.py` |
| `PageProjectionLimits` | `src/python/projectkoios/ingestion/page/projection/limits/definition.py` |
| `PageProjectionLimitError` | `src/python/projectkoios/ingestion/page/projection/limits/error.py` |
| `PageProjectionPage`, `PageProjectionPageInventory`, pure page derivation | `src/python/projectkoios/ingestion/page/projection/page.py` |
| `PageProjectionRequest`, request/canonical-page/verification freshness validation | `src/python/projectkoios/ingestion/page/projection/request.py` |
| `PageProjectionResult` | `src/python/projectkoios/ingestion/page/projection/result.py` |
| `PageProjectionPageWindowInventory` | `src/python/projectkoios/ingestion/page/projection/window.py` |
| enrichment closed enums | `src/python/projectkoios/ingestion/page/projection/enrichment/basis.py` |
| exact enrichment cross-binding | `src/python/projectkoios/ingestion/page/projection/enrichment/binding.py` |
| pure enrichment derivation | `src/python/projectkoios/ingestion/page/projection/enrichment/derivation.py` |
| enrichment identity values and inventories | `src/python/projectkoios/ingestion/page/projection/enrichment/identity.py` |
| complete entry inventory | `src/python/projectkoios/ingestion/page/projection/enrichment/inventory.py` |
| exact applicable limitation records | `src/python/projectkoios/ingestion/page/projection/enrichment/limitation.py` |
| exact producer bindings | `src/python/projectkoios/ingestion/page/projection/enrichment/producer.py` |
| available and unavailable entry records | `src/python/projectkoios/ingestion/page/projection/enrichment/record.py` |
| enrichment request/action/result | `src/python/projectkoios/ingestion/page/projection/enrichment/request.py`, `actionizer.py`, and `result.py` |
| exact opaque warning records | `src/python/projectkoios/ingestion/page/projection/enrichment/warning.py` |

Package initializers are docstring-only ownership markers and export no compatibility façade.

## Ownership exclusions

| Concern | Defining owner or disposition |
|---|---|
| paragraph/heading/caption values | typed block/style/inventory values under `page/projection` |
| path/media reads | external `artifact.managed.verification` action |
| source loading | an explicit reading-evidence source action |
| MongoDB query | reading-evidence Mongo source actionizer |
| transcript parsing and summary/baseline reconciliation | absent; `ReadingEvidenceSourceResult` is the canonical input |
| JSON report serialization/loading | absent |
| page and window access | semantic page and window inventories |
| alternate projection API | absent; no façade or alias exists |
| Search `EvidenceItem` construction | Search or downstream composition; enrichment contains no Search import |
| bibliography, asset linkage, citekey, authority status | References-owned input; absent from enrichment |
| claim support | human/domain authority; never inferred by enrichment |
| normalized caption raw-text selection | explicitly unavailable in enrichment v1; no arbitrary association choice |

Database schema migration is owned only by the Mongo reading-evidence migration hierarchy.
