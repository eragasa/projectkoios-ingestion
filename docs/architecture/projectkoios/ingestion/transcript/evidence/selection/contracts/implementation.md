# `selection.contracts` implementation

The request canonicalizes the bounded input-ID tuple and derives its identity
from that tuple and the exact transcript result. The result enforces the closed
outcome/evidence partition and derives its identity from request, producer,
outcome, ordered evidence, warning, and failure inventories.

```mermaid
flowchart LR
    Input["transcript + record IDs"] --> Request["request identity"]
    Request --> Outcome["closed outcome"]
    Outcome --> Result["result invariants"]
    Evidence["ordered evidence IDs"] --> Result
    Failures["failure/warning inventories"] --> Result
    Result --> Identity["result identity"]
```

Failed outcomes expose no page or block evidence. Only `EVIDENCE_AVAILABLE`
requires a complete canonical evidence inventory.
