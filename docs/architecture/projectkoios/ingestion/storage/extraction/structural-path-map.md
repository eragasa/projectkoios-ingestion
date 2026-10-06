# Storage structural path map

This is the reviewed inventory for the storage hierarchy migration. Source
paths in the first table are relative to `src/python/projectkoios/ingestion`.
Removed paths are not retained as aliases or re-export facades.

| Removed path | Direct owner path |
|---|---|
| `base/inventory/inventory.py` | `base/inventory/actionizer.py` |
| `base/materializer/materializer.py` | `base/materializer/actionizer.py` |
| `base/pipeline/pipeline.py` | `base/pipeline/actionizer.py` |
| `base/projector/inventory/inventory.py` | `base/projector/inventory/observer.py` |
| `base/projector/projector.py` | `base/projector/actionizer.py` |
| `integrations/mongodb/extraction/index_readiness.py` | `integrations/mongodb/extraction/index/readiness/backend.py` |
| `integrations/mongodb/extraction/materialization_error.py` | `integrations/mongodb/extraction/materialization/error.py` |
| `integrations/sqlite/processing_state/__init__.py` | `integrations/sqlite/processing/state/__init__.py` |
| `integrations/sqlite/processing_state/store.py` | `integrations/sqlite/processing/state/store.py` |
| `storage/extraction/artifact_validation/__init__.py` | `storage/extraction/artifact/validation/__init__.py` |
| `storage/extraction/artifact_validation/actionizer.py` | `storage/extraction/artifact/validation/actionizer.py` |
| `storage/extraction/artifact_validation/reader.py` | `storage/extraction/artifact/validation/reader/base.py` |
| `storage/extraction/artifact_validation/reader_error.py` | `storage/extraction/artifact/validation/reader/error.py` |
| `storage/extraction/artifact_validation/request.py` | `storage/extraction/artifact/validation/request.py` |
| `storage/extraction/artifact_validation/result.py` | `storage/extraction/artifact/validation/result.py` |
| `storage/extraction/bounded_freeze/__init__.py` | `storage/extraction/freeze/bounded/__init__.py` |
| `storage/extraction/bounded_freeze/actionizer.py` | `storage/extraction/freeze/bounded/actionizer.py` |
| `storage/extraction/bounded_freeze/error.py` | `storage/extraction/freeze/bounded/error.py` |
| `storage/extraction/bounded_freeze/extraction_error.py` | `storage/extraction/freeze/bounded/extraction/error.py` |
| `storage/extraction/bounded_freeze/extractor.py` | `storage/extraction/freeze/bounded/extractor.py` |
| `storage/extraction/bounded_freeze/request.py` | `storage/extraction/freeze/bounded/request.py` |
| `storage/extraction/bounded_freeze/result.py` | `storage/extraction/freeze/bounded/result.py` |
| `storage/extraction/bounded_freeze/source.py` | `storage/extraction/freeze/bounded/source/model.py` |
| `storage/extraction/bounded_freeze/source_reader.py` | `storage/extraction/freeze/bounded/source/reader.py` |
| `storage/extraction/bounded_freeze/store.py` | `storage/extraction/freeze/bounded/store.py` |
| `storage/extraction/identity_conflict_error.py` | `storage/extraction/identity/conflict/error.py` |
| `storage/extraction/journal_publication/__init__.py` | `storage/extraction/journal/publication/__init__.py` |
| `storage/extraction/journal_publication/actionizer.py` | `storage/extraction/journal/publication/actionizer.py` |
| `storage/extraction/journal_publication/backend.py` | `storage/extraction/journal/publication/backend/base.py` |
| `storage/extraction/journal_publication/backend_error.py` | `storage/extraction/journal/publication/backend/error.py` |
| `storage/extraction/journal_publication/request.py` | `storage/extraction/journal/publication/request.py` |
| `storage/extraction/journal_publication/result.py` | `storage/extraction/journal/publication/result.py` |
| `storage/extraction/materialization/collection_evidence.py` | `storage/extraction/materialization/evidence/collection.py` |
| `storage/extraction/materialization/evidence.py` | `storage/extraction/materialization/evidence/model.py` |
| `storage/extraction/projection/index_readiness/__init__.py` | `storage/extraction/projection/index/readiness/__init__.py` |
| `storage/extraction/projection/index_readiness/actionizer.py` | `storage/extraction/projection/index/readiness/actionizer.py` |
| `storage/extraction/projection/index_readiness/backend.py` | `storage/extraction/projection/index/readiness/backend/base.py` |
| `storage/extraction/projection/index_readiness/backend_error.py` | `storage/extraction/projection/index/readiness/backend/error.py` |
| `storage/extraction/projection/index_readiness/configuration.py` | `storage/extraction/projection/index/readiness/configuration.py` |
| `storage/extraction/projection/index_readiness/evidence.py` | `storage/extraction/projection/index/readiness/evidence/model.py` |
| `storage/extraction/projection/index_readiness/index.py` | `storage/extraction/projection/index/readiness/definition.py` |
| `storage/extraction/projection/index_readiness/index_evidence.py` | `storage/extraction/projection/index/readiness/evidence/index.py` |
| `storage/extraction/projection/index_readiness/request.py` | `storage/extraction/projection/index/readiness/request.py` |
| `storage/extraction/projection/index_readiness/result.py` | `storage/extraction/projection/index/readiness/result.py` |
| `storage/extraction/projection/inventory/inventory.py` | `storage/extraction/projection/inventory/observer.py` |
| `storage/extraction/projection/inventory/reader.py` | `storage/extraction/projection/inventory/reader/base.py` |
| `storage/extraction/projection/inventory/reader_error.py` | `storage/extraction/projection/inventory/reader/error.py` |
| `storage/extraction/projection/read_model.py` | `storage/extraction/projection/read/model.py` |
| `storage/extraction/projection_pipeline/__init__.py` | `storage/extraction/projection/pipeline/__init__.py` |
| `storage/extraction/projection_pipeline/configuration.py` | `storage/extraction/projection/pipeline/configuration.py` |
| `storage/extraction/projection_pipeline/pipeline.py` | `storage/extraction/projection/pipeline/actionizer.py` |
| `storage/extraction/projection_pipeline/request.py` | `storage/extraction/projection/pipeline/request.py` |
| `storage/extraction/projection_pipeline/result.py` | `storage/extraction/projection/pipeline/result.py` |
| `storage/extraction/selected_recovery/__init__.py` | `storage/extraction/recovery/subset/__init__.py` |
| `storage/extraction/selected_recovery/actionizer.py` | `storage/extraction/recovery/subset/actionizer.py` |
| `storage/extraction/selected_recovery/backend.py` | `storage/extraction/recovery/subset/backend/base.py` |
| `storage/extraction/selected_recovery/backend_error.py` | `storage/extraction/recovery/subset/backend/error.py` |
| `storage/extraction/selected_recovery/evidence.py` | `storage/extraction/recovery/subset/evidence.py` |
| `storage/extraction/selected_recovery/request.py` | `storage/extraction/recovery/subset/request.py` |
| `storage/extraction/selected_recovery/result.py` | `storage/extraction/recovery/subset/result.py` |
| `storage/processing_state/__init__.py` | `storage/processing/state/__init__.py` |
| `storage/processing_state/base.py` | `storage/processing/state/base.py` |
| `storage/processing_state/contracts.py` | `storage/processing/state/contracts.py` |
| `storage/processing_state/error.py` | `storage/processing/state/error.py` |

## Documentation path moves

These paths are relative to the repository root.

| Removed path | Direct owner path |
|---|---|
| `docs/architecture/projectkoios/ingestion/integrations/sqlite/processing_state/implementation.md` | `docs/architecture/projectkoios/ingestion/integrations/sqlite/processing/state/implementation.md` |
| `docs/architecture/projectkoios/ingestion/integrations/sqlite/processing_state/index.md` | `docs/architecture/projectkoios/ingestion/integrations/sqlite/processing/state/index.md` |
| `docs/architecture/projectkoios/ingestion/integrations/sqlite/processing_state/schematic.md` | `docs/architecture/projectkoios/ingestion/integrations/sqlite/processing/state/schematic.md` |
| `docs/architecture/projectkoios/ingestion/storage/processing_state/implementation.md` | `docs/architecture/projectkoios/ingestion/storage/processing/state/implementation.md` |
| `docs/architecture/projectkoios/ingestion/storage/processing_state/index.md` | `docs/architecture/projectkoios/ingestion/storage/processing/state/index.md` |
| `docs/architecture/projectkoios/ingestion/storage/processing_state/schematic.md` | `docs/architecture/projectkoios/ingestion/storage/processing/state/schematic.md` |

## Test path moves

These paths are relative to `tests/projectkoios/ingestion`.

| Removed path | Direct owner path |
|---|---|
| `storage/extraction/artifact_validation/test__ExistingExtractionArtifactValidationActionizer.py` | `storage/extraction/artifact/validation/test__ExistingExtractionArtifactValidationActionizer.py` |
| `storage/extraction/bounded_freeze/test__BoundedExtractionFreezeActionizer.py` | `storage/extraction/freeze/bounded/test__BoundedExtractionFreezeActionizer.py` |
| `storage/extraction/journal_publication/test__ValidatedExtractionJournalPublicationActionizer.py` | `storage/extraction/journal/publication/test__ValidatedExtractionJournalPublicationActionizer.py` |
| `storage/extraction/projection/index_readiness/test__ExtractionProjectionIndexReadinessActionizer.py` | `storage/extraction/projection/index/readiness/test__ExtractionProjectionIndexReadinessActionizer.py` |
| `storage/extraction/projection_pipeline/test__ExtractionProjectionMaterializationPipeline.py` | `storage/extraction/projection/pipeline/test__ExtractionProjectionMaterializationPipeline.py` |
| `storage/processing_state/conftest.py` | `storage/processing/state/conftest.py` |
| `storage/processing_state/test__AbstractProcessingStateStore.py` | `storage/processing/state/test__AbstractProcessingStateStore.py` |
| `storage/processing_state/test__ProcessingStateContracts.py` | `storage/processing/state/test__ProcessingStateContracts.py` |
| `storage/processing_state/test__SqliteProcessingStateStore.py` | `storage/processing/state/test__SqliteProcessingStateStore.py` |

## Unstable subset-recovery API

The former selected-recovery API is intentionally replaced rather than adapted:

- `SelectedExtractionProjectionRecovery*` becomes
  `ExtractionProjectionSubsetRecovery*`;
- `selected_records`, `selected_record_count`, and `last_selected_sequence`
  become `subset_records`, `subset_record_count`, and `last_subset_sequence`;
- `recover_selected()` becomes `recover_subset()`; and
- contract names, stable-ID namespaces, failure codes, messages, fixtures, and
  documentation use `extraction-projection-subset-recovery` terminology.

These contracts are explicitly unstable. There is no legacy decoder, alias, or
compatibility facade.
