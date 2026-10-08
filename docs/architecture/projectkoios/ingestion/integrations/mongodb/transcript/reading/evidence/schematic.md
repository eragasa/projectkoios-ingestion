# MongoDB reading-evidence schematic

```text
ReadingEvidenceProjectionResult
             |
             v
MongoReadingEvidenceMaterializationRequest
             |
             v
create-once generation-scoped records
 documents -> pages -> blocks/evidence -> references
 in bounded batches; no generation-wide transaction
             |
             v
reconstruct + independently verify
             |
             v
create immutable MongoReadingEvidenceCompletionManifest last
             |
             v
MongoReadingEvidenceSourceActionizer
 only current-schema completed generations are visible
```

```text
old schema + frozen source inventory + typed adjacent-step registry
             |
             v
bounded side-by-side migration requests/results
             |
             v
independent source/target inventory and equivalence verification
             |
             v
conditional create-once migration completion manifest
             |
             v
separately authorized reader cutover
```

Workflow owns iteration, retry, checkpoint, cleanup, cutover, and rollback decisions.
