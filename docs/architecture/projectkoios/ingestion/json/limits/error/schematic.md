# `json.limits.error` schematic

```mermaid
flowchart LR
    Boundary["configured JsonLimits"]
    Operation["parse / project / serialize"]
    Error["JsonLimitError"]
    Domain["optional domain error translation"]

    Boundary --> Operation
    Operation --> Error
    Error --> Domain
```

Rejected payload content is not embedded in the generic error.
