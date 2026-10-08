# `json.error` schematic

```mermaid
flowchart LR
    Parse["JsonParser"]
    Serialize["JsonValueProjector / JsonSerializer"]
    ParseError["JsonParseError"]
    DuplicateError["JsonDuplicateFieldError"]
    SerializationError["JsonSerializationError"]
    Domain["optional domain translation"]

    Parse --> ParseError --> Domain
    Parse --> DuplicateError --> ParseError
    Serialize --> SerializationError --> Domain
```

Limit exhaustion follows the separate `JsonLimitError` path.
