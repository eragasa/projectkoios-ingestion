# `projectkoios.ingestion.page.projection` structural path map

| Prototype concern | Clean defining owner |
|---|---|
| path-taking `validate_page_projection(...)` | `PageProjectionRequest -> PageProjectionActionizer -> PageProjectionResult` |
| paragraph/heading/caption dictionaries | typed block/style/inventory values under `page/projection` |
| path/media reads | external `artifact.managed.verification` action |
| transcript parsing and summary/baseline reconciliation | removed; canonical `ReadingEvidenceDocument` is the only input |
| MongoDB query | reading-evidence Mongo source actionizer |
| validation report serialization/loading | removed |
| module helper identities | bounded page input/result identity derivations |
| page/window iterators | semantic inventory iteration/window value |
| flat `page_projection.py` | deleted after consumer migration; no façade |

The replacement intentionally does not preserve prototype paths, formats, IDs, reports, thresholds, or decoder behavior. Database schema migration is owned only by the Mongo reading-evidence migration hierarchy.
