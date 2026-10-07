# `pdf.batch.json` schematic

```mermaid
flowchart LR
    Content["bounded UTF-8 JSON"]
    Parser["ingestion.json.JsonParser"]
    Value["JsonValue"]
    Contract["PdfBatchPlanJsonContract"]
    Item["PdfBatchItem"]
    Plan["PdfBatchPlan"]
    Serializer["ingestion.json.JsonSerializer"]

    Content --> Parser --> Value --> Contract
    Contract --> Item --> Plan
    Plan --> Contract --> Serializer --> Content
```

The generic JSON package owns safe mechanics. The PDF batch specialization owns
only field schema, record reconstruction, formatting selection, and domain error
translation.
