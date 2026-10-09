# COCO layout integration schematic

```text
verified managed image bytes + verified pinned model bytes
        │
        ├─ exact preprocessing + runtime/provider/device identities
        ├─ canonical non-media request document + output-byte bound
        └─ exact raw output bytes + elapsed nanoseconds + failure evidence
        │
        v
CocoLayoutDetectorInvocationResult
        │
        v
CocoLayoutDetectorOutputParser
        │ strict canonical parsing + exact invocation binding
        v
CocoLayoutDetectorOutputParsingResult (VALID)
        │
        v
CocoLayoutDetectorObservationInventory
        │ model label ID, xyxy box, confidence, producer order
        │
        ├─ exact model resource + runtime identity
        ├─ explicit model-label disposition registry
        └─ confidence threshold + hard observation bound
        │
        v
CocoLayoutDetectorObservationActionizer
        ├─ accepted -> canonical contiguous COCO annotation IDs
        └─ unsupported/below-threshold -> explicit limitations
        │
        v
CocoLayoutDetectionInventory
        │
        ├─ CocoLayoutImage -> exact LayoutPageRenderEvidence
        └─ CocoLayoutProposalConfiguration
              ├─ Koios COCO Layout Profile v0.1
              ├─ pinned DocLayNet category-registry identity
              ├─ detector + runtime versions
              └─ model resource identity + SHA-256
        │
        v
CocoLayoutProposalRequest
        │
        v
CocoLayoutRegionProposalActionizer
        │ one-to-one deterministic xywh -> x1y1x2y2 adaptation
        v
CocoLayoutProposalResult
        ├─ exact LayoutRegionProposalSource
        └─ CocoLayoutProposalAdaptationInventory
              └─ backend-neutral LayoutRegionProposal
        │
        ├───────────────> DeterministicLayoutReviewActionizer
        │                           │
        │                           v
        │                 CocoLayoutDetectorGateActionizer
        │                   │ requires the exact VALID parsing result
        │                   ├─ admitted -> deterministic page-finalizer input
        │                   └─ unresolved -> bounded escalation candidate
        │
        ├───────────────> CocoLayoutRegionAdmissionActionizer
        │                   │ exact VALID parsing + proposal evidence
        │                   ├─ one independent outcome per profile category
        │                   ├─ unsupported labels remain limitations
        │                   └─ Formula admitted
        │                         -> equation candidate projection
        │                         -> verified region assembly
        │                         -> recognition-ready evidence
        │
        v
CocoLayoutBundle.create
        ├─ annotations.coco.json
        │    └─ images + categories + boxes + scores
        ├─ reading-order.json
        │    └─ complete order per image + annotations SHA-256
        ├─ lineage.json
        │    └─ detection/proposal/adaptation/native-block lineage
        └─ manifest.json
             └─ exact member IDs + SHA-256 + lengths + media types
```

```text
four canonical member byte sequences
        │ strict bounded parse and canonical replay
        v
CocoLayoutBundle.from_member_bytes
        │
        ├─ annotation/category/image validation
        ├─ exact reading-order coverage
        ├─ exact lineage coverage and identity reconstruction
        └─ manifest digest/length/document verification
```

COCO never carries Koios authority, model agreement, human review, or
publication decisions. Reading order, native-block membership, and lineage are
Koios sidecars rather than overloaded COCO fields.
