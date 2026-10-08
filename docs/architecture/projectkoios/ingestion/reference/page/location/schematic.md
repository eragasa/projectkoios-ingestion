# Reference page-location schematic

```text
ReferenceEvidenceRecord + CleanTranscript + page index
    + ReferenceTopicAnchorInventory
        │
        v
LocatorProjectionRequest -> LocatorProjectionActionizer -> ReferencePageLocator
                                                               │
ReferenceEvidenceRecord + CleanTranscript + locator ───────────┘
        │
        v
PageLocationRequest -> PageLocationActionizer -> ReferencePageLocatorResult
                     │                         (semantic identity inventories;
                     └-> anchor inventory       payload-free navigation evidence)
                         match partition
```
