# `projectkoios.ingestion.transcript.reading.evidence` schematic

```text
ReadingDocumentProducerEvidence
ReadingPageTextProducerEvidenceInventory
structured-item + clean-text producer inventories
figure/table/equation producer inventories
ManagedArtifactReferenceInventory
                 |
                 v
ReadingEvidenceProjectionRequest
                 |
                 v
ReadingEvidenceProjectionActionizer (pure)
 exact identity join
 clean text + structured role/order
 visual/equation join and gates
                 |
                 v
ReadingEvidenceProjectionResult
 + ReadingEvidenceDocument
 + recomputed ReadingEvidenceInventory
 + ReadingEvidenceReconciliation
                 |
          +------+------+
          |             |
          v             v
MongoDB materialize   equivalence verify
          |
          v
ReadingEvidenceSourceResult
          |
          v
PageProjectionRequest
 + ManagedArtifactVerificationEvidenceInventory
          |
          v
PageProjectionActionizer (pure)
```

Workflow owns retries, batching, checkpoints, approvals, and migration orchestration. Search owns chunks, embeddings, and ranking.
