# `projectkoios.ingestion.pdf.batch` schematic

```mermaid
flowchart LR
    Corpus["PDF corpus preparation"]
    Item["pdf.batch.item<br/>PdfBatchItem"]
    Plan["pdf.batch.plan<br/>PdfBatchPlan"]
    Limits["pdf.batch.limits<br/>resource bounds"]
    Commands["PDF / equation / transcript / OCR commands"]
    Verify["effectful source verification"]
    Extract["PDF extraction owners"]
    Publish["artifact publication owners"]
    Workflow["Workflow lifecycle"]

    Limits --> Item
    Limits --> Plan
    Corpus --> Item
    Item --> Plan
    Plan --> Commands
    Commands --> Verify
    Verify --> Extract
    Extract --> Publish
    Workflow -. schedules .-> Commands
```

The item and plan are immutable portable input records. They declare source
checksums and relative targets but perform no I/O. Commands and other effectful
owners verify external state before extraction or publication. Workflow may
schedule a command as a prototask but does not become part of the plan record.
