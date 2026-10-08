# `projectkoios.ingestion.page.projection` schematic

```text
ReadingEvidenceSourceResult
             +
ManagedArtifactVerificationResult
             |
             v
PageProjectionRequest
 current ReadingEvidenceDocument
 exact verification coverage
             |
             v
PageProjectionActionizer (pure)
             |
             v
PageProjectionResult
 paragraph + heading + unique figure-caption text
             |
             v
Search-owned downstream admission/chunking
```

The prototype `page_projection.py`, JSONL layouts, reports, and IDs are not inputs or compatibility targets.
