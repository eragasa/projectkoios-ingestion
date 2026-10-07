# `projectkoios.ingestion.json` schematic

```mermaid
flowchart LR
    Record["typed immutable record"]
    DomainContract["domain JsonContract[T]"]
    Value["JsonValue"]
    Parser["JsonParser"]
    Serializer["JsonSerializer"]
    Limits["JsonLimits"]
    Bytes["bounded UTF-8 bytes/text"]
    Canonical["CanonicalJsonSerializer"]
    Identity["stable-ID owner"]
    CLI["CLI presentation JSON"]
    Backend["integration transport JSON"]

    Limits --> Parser
    Limits --> Serializer
    Record --> DomainContract
    DomainContract --> Value
    Parser --> DomainContract
    DomainContract --> Serializer
    Bytes --> Parser
    Serializer --> Bytes
    Record --> Canonical --> Identity
    CLI -. may use serializer only .-> Serializer
    Backend -. may use parser only .-> Parser
```

A domain JSON contract owns record-specific field schema and reconstruction.
The generic package owns bounded JSON mechanics. CLI presentation and backend
transport may reuse those mechanics without being misclassified as durable
record contracts.
