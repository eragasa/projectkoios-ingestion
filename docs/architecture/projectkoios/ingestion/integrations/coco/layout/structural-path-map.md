# COCO layout structural path map

| Semantic owner | Defining path |
| --- | --- |
| COCO category and registry | `integrations/coco/layout/category.py` |
| Koios COCO Layout Profile v0.1 | `integrations/coco/layout/profile.py` |
| COCO image/render binding | `integrations/coco/layout/image.py` |
| COCO detection and inventory | `integrations/coco/layout/detection.py` |
| Typed annotation document | `integrations/coco/layout/document.py` |
| Detector/profile configuration | `integrations/coco/layout/configuration.py` |
| Local detector model resource | `integrations/coco/layout/detector/resource.py` |
| Local detector label mapping | `integrations/coco/layout/detector/label.py` |
| Raw local detector observations | `integrations/coco/layout/detector/observation.py` |
| Local detector adaptation configuration | `integrations/coco/layout/detector/configuration.py` |
| Local detector adaptation request | `integrations/coco/layout/detector/request.py` |
| Local detector exclusions | `integrations/coco/layout/detector/limitation.py` |
| Observation/detection lineage | `integrations/coco/layout/detector/adaptation.py` |
| Local detector adaptation result | `integrations/coco/layout/detector/result.py` |
| Local detector adaptation actionizer | `integrations/coco/layout/detector/actionizer.py` |
| Detector preprocessing evidence | `integrations/coco/layout/detector/invocation/preprocessing.py` |
| Exact detector invocation request | `integrations/coco/layout/detector/invocation/request.py` |
| Exact detector invocation result | `integrations/coco/layout/detector/invocation/result.py` |
| Detector invocation provider port | `integrations/coco/layout/detector/invocation/provider.py` |
| Detector invocation actionizer | `integrations/coco/layout/detector/invocation/actionizer.py` |
| Verified ONNX Runtime provider | `integrations/coco/layout/detector/invocation/onnx.py` |
| Canonical detector raw output | `integrations/coco/layout/detector/invocation/output.py` |
| Detector output parsing request | `integrations/coco/layout/detector/invocation/parsing/request.py` |
| Detector output parsing status | `integrations/coco/layout/detector/invocation/parsing/status.py` |
| Detector output parsing derivation | `integrations/coco/layout/detector/invocation/parsing/derivation.py` |
| Detector output parsing result | `integrations/coco/layout/detector/invocation/parsing/result.py` |
| Detector output parser | `integrations/coco/layout/detector/invocation/parsing/actionizer.py` |
| Detector admission policy | `integrations/coco/layout/detector/gate/configuration.py` |
| Detector admission request | `integrations/coco/layout/detector/gate/request.py` |
| Detector admission status and reasons | `integrations/coco/layout/detector/gate/reason.py` |
| Detector admission result | `integrations/coco/layout/detector/gate/result.py` |
| Detector admission actionizer | `integrations/coco/layout/detector/gate/actionizer.py` |
| Adaptation request | `integrations/coco/layout/request.py` |
| Detection/proposal adaptation | `integrations/coco/layout/adaptation.py` |
| Adaptation result | `integrations/coco/layout/result.py` |
| Adaptation actionizer | `integrations/coco/layout/actionizer.py` |
| Reading-order sidecar | `integrations/coco/layout/reading/order.py` |
| Proposal/native-block lineage sidecar | `integrations/coco/layout/lineage.py` |
| Bundle manifest | `integrations/coco/layout/manifest.py` |
| Complete bundle verification | `integrations/coco/layout/bundle.py` |
| Shared canonical JSON mechanics | `integrations/coco/layout/json/base.py` |
| COCO annotations JSON | `integrations/coco/layout/json/annotations.py` |
| Reading-order JSON | `integrations/coco/layout/json/reading/order.py` |
| Lineage JSON | `integrations/coco/layout/json/lineage.py` |
| Manifest JSON | `integrations/coco/layout/json/manifest.py` |
| JSON value validation | `integrations/coco/layout/json/value.py` |
| Hard bounds | `integrations/coco/layout/limits/definition.py` |
| Bound failures | `integrations/coco/layout/limits/error.py` |

This hierarchy is additive. It does not move or alias the existing
`layout.proposal`, `layout.review`, or `integrations.layout_parser` contracts.
