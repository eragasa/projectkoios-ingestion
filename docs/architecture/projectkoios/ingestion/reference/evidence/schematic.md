# `projectkoios.ingestion.reference.evidence` schematic

```mermaid
flowchart LR
    Extraction["completed extraction + exact bytes"]
    Transcript["automated-unreviewed clean transcript + exact bytes"]
    Audit["recorded passing audit + exact bytes"]
    ProjectionRequest["projection.request"]
    ProjectionAction["projection.actionizer"]
    Record["reference.evidence.record<br/>action result"]
    Json["reference.evidence.json<br/>ReferenceEvidenceJsonContract"]
    SharedJson["ingestion.json<br/>bounded mechanics"]
    VerifyRequest["verification.request"]
    VerifyAction["verification.actionizer"]
    VerifyResult["verification.result"]
    Consumer["injected references consumer"]
    Authority["human acceptance / publication"]

    Extraction --> ProjectionRequest
    Transcript --> ProjectionRequest
    Audit --> ProjectionRequest
    ProjectionRequest --> ProjectionAction
    ProjectionAction --> Record
    Record --> Json
    SharedJson --> Json
    Json --> Consumer
    Record --> VerifyRequest
    Consumer --> VerifyRequest
    VerifyRequest --> VerifyAction
    VerifyAction --> VerifyResult
    Authority -. remains external .-> Consumer
```

Projection is pure and binds already-produced evidence. The JSON contract is
reversible and byte-exact. Verification checks source and optional artifact
identity but does not independently establish extraction accuracy, semantic
correctness, audit validity, acceptance, or publication authority.
