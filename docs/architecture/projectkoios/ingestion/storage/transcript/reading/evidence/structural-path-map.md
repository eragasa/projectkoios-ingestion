# Reading-evidence storage structural path map

This clean slice introduces backend-neutral owners and narrows previously planned MongoDB owners. No runtime compatibility façade is retained.

| Prior planned owner | Current defining leaf |
| --- | --- |
| `integrations.mongodb.transcript.reading.evidence.schema.version.MongoReadingEvidenceSchemaVersion` | `storage.transcript.reading.evidence.schema.version.ReadingEvidenceStorageSchemaVersion` |
| `integrations.mongodb.transcript.reading.evidence.manifest.MongoReadingEvidenceCompletionManifest` | `storage.transcript.reading.evidence.completion.manifest.ReadingEvidenceCompletionManifest` |
| Mongo-owned document/page/block/evidence record encoding | `storage.transcript.reading.evidence.json.contract.ReadingEvidenceStorageJsonContract` |
| Mongo-owned generation record model | `storage.transcript.reading.evidence.projection.document.ReadingEvidenceStorageDocument` |
| Mongo-owned complete generation | `storage.transcript.reading.evidence.projection.read.model.ReadingEvidenceReadModel` |
| Mongo-owned canonical decomposition | `storage.transcript.reading.evidence.projection.projector.ReadingEvidenceStorageProjector` |
| `integrations.mongodb.transcript.reading.evidence.source.verification.MongoReadingEvidenceSourceVerifier` | `storage.transcript.reading.evidence.source.verifier.ReadingEvidenceReadModelVerifier` |
| Mongo-owned materialization semantics | `storage.transcript.reading.evidence.materialization.actionizer.ReadingEvidenceMaterializer` port |
| Mongo-owned source document semantics | `storage.transcript.reading.evidence.source.reader.ReadingEvidenceReadModelReader` port |
| `integrations.mongodb.transcript.reading.evidence.materialization.actionizer.MongoReadingEvidenceMaterializer` | same path, narrowed to physical MongoDB writes |
| `integrations.mongodb.transcript.reading.evidence.source.actionizer.MongoReadingEvidenceSourceActionizer` | same path, narrowed to MongoDB reads plus neutral verification composition |
| `storage.transcript.reading.evidence.projection.document.ReadingEvidenceStorageDocumentInventory` (draft) | `storage.transcript.reading.evidence.projection.inventory.ReadingEvidenceStorageDocumentInventory` |
| Monolithic draft record graph codec internals | `projection.record.block.codec.ReadingEvidenceStorageBlockCodec`, `projection.record.header.codec.ReadingEvidenceStorageHeaderCodec`, `projection.record.graph.encoder.ReadingEvidenceStorageRecordGraphEncoder`, and `projection.record.graph.decoder.ReadingEvidenceStorageRecordGraphDecoder` |
| Inline typed-JSON registry inside the draft contract | `storage.transcript.reading.evidence.json.registry` focused module |

New defining leaves are imported directly. Package initializers remain docstring-only markers.
