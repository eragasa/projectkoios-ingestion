# Docling integration schematic

```text
exact render identity + upstream evidence identity
        │
        ├─ page pixel dimensions
        ├─ explicit left-to-right/right-to-left direction
        └─ producer-ordered semantic elements
             └─ stable ID + Koios kind + exact pixel box
        │
        v
DoclingReadingOrderRequest
        │
        ├─ pinned docling-slim 2.135.0
        ├─ pinned docling-core 2.101.1
        ├─ pinned Rtree 1.4.1
        └─ reading_order_rb
        │
        v
InstalledDoclingReadingOrderProvider
        │ vendor types remain internal
        v
raw element-ID sequence
        │
        ├─ exact tuple type
        ├─ no unknown IDs
        ├─ no duplicate IDs
        └─ complete request permutation
        │
        v
DoclingReadingOrderResult
        ├─ candidate_produced -> verification required
        └─ unresolved -> closed failure kind
```

```text
candidate + exact geometry/membership evidence
        │
        v
planned deterministic verifier/resolver
        ├─ mechanically unique -> resolved order evidence
        └─ ambiguous/conflicting/incomplete -> escalation
```

The Docling result is never publication authority and never directly populates
the COCO `reading-order.json` sidecar.
