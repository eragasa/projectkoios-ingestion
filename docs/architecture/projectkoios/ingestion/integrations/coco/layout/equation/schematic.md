# COCO layout equation projection schematic

```text
CocoLayoutRegionAdmissionResult
        │
        └─ Formula category (ADMITTED)
              ├─ exact invocation/parsing/detector/proposal lineage
              ├─ LayoutPageRenderEvidence + LayoutPixelMapping
              └─ CocoLayoutEquationProjectionConfiguration
                    │
                    v
CocoLayoutEquationProjectionRequest
        │
        v
CocoLayoutEquationProjectionActionizer
        ├─ consume only category-admitted Formula detections
        ├─ stronger equation threshold -> explicit confidence exclusion
        ├─ deterministic confidence-first IoU suppression
        │      └─ explicit duplicate exclusion
        ├─ pixel xyxy -> source-page affine corner envelope
        ├─ bounded source padding clipped to page bounds
        └─ canonical page-position ordering
        │
        v
CocoLayoutEquationProjectionResult
        ├─ CocoLayoutEquationCandidateEvidenceInventory
        └─ CocoLayoutEquationExclusionInventory
        │
        v
CocoLayoutEquationAssembler + PageRegionRenderer
        ├─ verify current source bytes
        ├─ render exact padded source region
        └─ verify render source/page/region/renderer lineage
        │
        v
EquationAssemblyResult (DISPLAY, recognition-ready)
        │
        └─ optional recognizer -> LaTeX/MathML proposal evidence
```

Neither category admission, projection, nor assembly finalizes page layout,
accepts a transcription, or grants publication authority.
