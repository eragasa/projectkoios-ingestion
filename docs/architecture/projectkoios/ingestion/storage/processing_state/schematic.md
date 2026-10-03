# Processing-state storage schematic

```mermaid
flowchart LR
    Registration["ProcessingStateInitializationRequest"]
    Load["ProcessingStateLoadRequest"]
    Snapshot["ProcessingStateSnapshot"]
    Save["ProcessingStateSaveRequest"]
    Store["AbstractProcessingStateStore"]
    Result["ProcessingStateSaveResult"]
    Adapter["backend adapter"]

    Registration --> Store
    Load --> Store
    Store --> Snapshot
    Snapshot --> Save
    Save --> Store
    Store --> Result
    Store --> Adapter
```

Only the backend adapter owns persistence-specific commands and transaction
objects. A workflow derives a complete next snapshot and submits it with the
exact snapshot identity it observed.
