# Reading-evidence storage schematic

```text
ReadingEvidenceProjectionResult
             |
             v
ReadingEvidenceStorageProjector (pure)
             |
             v
ReadingEvidenceReadModel
  document/page/block/producer/reference/limitation members
  + completion manifest
             |
             +---------------------------+
             |                           |
             v                           v
ReadingEvidenceMaterializer port   backend-neutral expected inventory
             |
       disk | SQLite | MongoDB adapters
```

```text
ReadingEvidenceReadModelReader port
             |
             v
bounded ReadingEvidenceReadModel
             |
             v
ReadingEvidenceReadModelVerifier (pure)
  strict current-schema decode
  typed reconstruction
  independent inventory observation
  manifest/document/inventory/projection checks
             |
             v
ReadingEvidenceSourceResult
```

```text
verified reference source + verified observed source + optional replay evidence
                                  |
                                  v
                  ReadingEvidenceEquivalenceVerifier
                                  |
                                  v
                   technical equivalence result
```

Adapters own physical I/O only. Workflow owns lifecycle and migration orchestration.
