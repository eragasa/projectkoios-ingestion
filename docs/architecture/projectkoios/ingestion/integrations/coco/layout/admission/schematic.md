# COCO layout region admission schematic

```text
VALID parsed detector evidence + exact COCO proposals
                         │
                         v
              exact lineage verification
                         │
                         v
            partition by profile category
                         │
          ┌──────────────┼──────────────┐
          v              v              v
      confidence    same-kind IoU    count bound
          │              │              │
          └──────────────┼──────────────┘
                         v
       one independent outcome per profile category
          ├─ admitted
          ├─ empty
          └─ escalation_required
                         │
                         v
       category-specific deterministic projectors
```

Detector limitations remain exact evidence. No category outcome grants
whole-page or publication authority.
