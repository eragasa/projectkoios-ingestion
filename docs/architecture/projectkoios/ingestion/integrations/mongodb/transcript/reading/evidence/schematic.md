# MongoDB reading-evidence schematic

```text
MongoReadingEvidenceIndexReadinessActionizer
  create or exactly verify configured scope indexes
             |
             v
MongoDB physical collections ready for bounded access
```

```text
ReadingEvidenceReadModel (already projected, backend-neutral)
             |
             v
MongoReadingEvidenceMaterializer
  validate capability/target and BSON bounds
  create or exactly replay child members
  create or exactly replay completion member last
             |
             v
MongoDB physical collections
```

```text
MongoReadingEvidenceSourceActionizer
             |
             v
MongoReadingEvidenceReadModelReader
  require completion member
  bounded exact generation reads
             |
             v
ReadingEvidenceReadModel (backend-neutral)
             |
             v
ReadingEvidenceReadModelVerifier (pure, backend-neutral)
             |
             v
ReadingEvidenceSourceResult
```

MongoDB owns transport and physical persistence only. Workflow owns lifecycle and migration orchestration.
