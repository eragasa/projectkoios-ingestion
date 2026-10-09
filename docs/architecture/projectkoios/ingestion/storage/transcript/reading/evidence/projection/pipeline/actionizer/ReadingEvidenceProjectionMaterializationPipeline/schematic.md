# `ReadingEvidenceProjectionMaterializationPipeline` schematic

```text
ReadingEvidenceStorageProjectionSource
                 |
                 v
ReadingEvidenceStorageProjector (pure)
                 |
                 v
ReadingEvidenceReadModel
                 |
                 v
ReadingEvidenceMaterializer (effectful port)
                 |
                 v
ReadingEvidenceProjectionPipelineResult
```
