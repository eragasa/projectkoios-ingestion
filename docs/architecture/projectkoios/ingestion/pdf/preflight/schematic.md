# `projectkoios.ingestion.pdf.preflight` schematic

```mermaid
flowchart LR
    Request["source + bounded selections"]
    Hook["backend planning hook<br/>primitive measurements"]
    Policy["preflight policy"]
    Plan["immutable allocation plan"]
    Template["PdfRegionRenderer template"]

    Request --> Policy
    Hook --> Policy
    Policy --> Plan
    Plan --> Template
```

Only primitive facts from backend planning hooks enter preflight; backend
document, page, rectangle, matrix, pixmap, and colorspace objects do not.
