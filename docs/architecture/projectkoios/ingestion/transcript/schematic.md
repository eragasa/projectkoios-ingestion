# `projectkoios.ingestion.transcript` schematic

```mermaid
flowchart LR
    Owners["ingestion owner artifacts"]
    Transcript["structured and clean transcripts"]
    Package["transcript package"]
    Batch["transcript.batch"]
    Evidence["transcript.evidence"]

    Owners --> Batch
    Batch --> Transcript
    Transcript --> Evidence
    Package --> Batch
    Package --> Evidence
```

The package is an ownership boundary, not a second transcript representation.
