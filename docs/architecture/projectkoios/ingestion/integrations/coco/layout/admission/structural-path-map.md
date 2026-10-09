# COCO layout region admission structural path map

| Semantic owner | Defining path |
| --- | --- |
| Default profile-wide admission policy and bounds | `integrations/coco/layout/admission/configuration.py` |
| Exact detector/proposal admission request | `integrations/coco/layout/admission/request.py` |
| Per-detection disposition evidence and inventory | `integrations/coco/layout/admission/evidence.py` |
| Per-category status, outcome, and inventory | `integrations/coco/layout/admission/outcome.py` |
| Shared deterministic COCO box overlap | `integrations/coco/layout/admission/overlap.py` |
| Complete result, coverage, and pure derivation | `integrations/coco/layout/admission/result.py` |
| Admission actionizer | `integrations/coco/layout/admission/actionizer.py` |

The full-page detector gate remains separately defined under
`integrations/coco/layout/detector/gate/`.
