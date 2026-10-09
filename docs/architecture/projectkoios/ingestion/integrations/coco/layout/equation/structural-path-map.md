# COCO layout equation projection structural path map

| Semantic owner | Defining path |
| --- | --- |
| Projection configuration and hard bounds | `integrations/coco/layout/equation/configuration.py` |
| Category-admitted projection request and lineage validation | `integrations/coco/layout/equation/request.py` |
| Candidate evidence and candidate inventory | `integrations/coco/layout/equation/candidate.py` |
| Confidence/duplicate exclusions and exclusion inventory | `integrations/coco/layout/equation/exclusion.py` |
| Projection result and pure deterministic derivation | `integrations/coco/layout/equation/result.py` |
| Projection actionizer | `integrations/coco/layout/equation/actionizer.py` |
| Recognition-ready rendered assembly | `integrations/coco/layout/equation/assembler.py` |
| Pixel-to-source affine box mapping | `layout/render/mapping.py` |

The hierarchy is additive. It does not move, alias, or replace equation
detection, assembly, recognition, generic COCO category admission, the
whole-page detector gate, or layout-resolution contracts.
