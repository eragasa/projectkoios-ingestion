# Layout review structural path map

The branch first corrected proposal ownership, then independent review exposed a
required architectural refinement. This map records both changes. The
provisional contracts are unpublished; no compatibility façade or legacy
decoder is retained.

## Proposal ownership correction

| Previous provisional path | Defining path | Ownership |
|---|---|---|
| `layout/review/evidence/render.py` | `layout/render/evidence.py` | Exact rendered-page identity |
| proposal symbols in `layout/review/kind.py` | `layout/proposal/kind.py` | Backend-neutral region taxonomy |
| `layout/review/evidence/source.py` | `layout/proposal/source.py` | Detector and model resource identity |
| `layout/review/proposal.py` | `layout/proposal/region.py` | Unaccepted region proposal |

## Implemented refinement

| Replaced provisional path or responsibility | Defining path | Ownership |
|---|---|---|
| dimension-derived render geometry in `layout/render/evidence.py` | `layout/render/mapping.py` | Exact affine pixel/source mapping |
| render-specific values mixed with shared limits | `layout/render/limits/definition.py` | Raster dimension and pixel-area bounds |
| render-specific limit failures mixed with shared errors | `layout/render/limits/error.py` | Render limit failure |
| global block partitions in `layout/review/result.py` | `layout/review/block.py` | One normalized review-evidence record per native block |
| repeated global overlap scans in `layout/review/actionizer.py` | `layout/review/actionizer.py` | One bounded proposal scan per block |
| dimension-ratio mapping in `layout/review/overlap.py` | `layout/review/overlap.py` | Affine-mapped block/proposal intersection |
| reading-order graph traversal in `layout/annotation/collection.py` | `layout/annotation/order.py` | Bounded duplicate-edge and cycle validation |
| loose detection/proposal relation in `integrations/layout_parser/result.py` | `integrations/layout_parser/adaptation.py` | One typed detection-to-proposal derivation |
| unbounded adapter label map | `integrations/layout_parser/limits/definition.py` | Adapter-specific label and mapping bounds |
| adapter limit failures mixed with proposal limits | `integrations/layout_parser/limits/error.py` | LayoutParser adaptation limit failure |
| arbitrary proposal/source inputs in `integrations/layout_parser/result.py` | `integrations/layout_parser/result.py` | Complete request plus ordered adaptations |

## Retained defining paths

| Defining path | Ownership |
|---|---|
| `layout/proposal/limits/definition.py` | Proposal count bounds |
| `layout/proposal/limits/error.py` | Proposal limit failure |
| `layout/review/configuration.py` | Review thresholds and cost bounds |
| `layout/review/request.py` | Complete comparison request |
| `layout/review/result.py` | Request-bound prepared review case |
| `layout/annotation/kind.py` | Evidence-author-neutral outcome and failure taxonomy |
| `layout/annotation/region.py` | Corrected region and block membership |
| `layout/annotation/failure.py` | Observed failure label |
| `layout/annotation/validation.py` | Shared structural annotation validation |
| `layout/annotation/collection.py` | Complete human annotation evidence |
| `layout/annotation/model/` | Exact model invocation, parsing, limitation, and replicated resolution evidence |
| `layout/annotation/human/evidence.py` | Optional terminal human review over exact model resolution |
| `layout/annotation/limits/definition.py` | Annotation collection bounds |
| `layout/annotation/limits/error.py` | Annotation limit failure |
| `layout/validation/value.py` | Shared layout value validation |
| `layout/limits/definition.py` | Shared identity-field and coordinate bounds |
| `integrations/layout_parser/detection.py` | Frozen vendor detection record |
| `integrations/layout_parser/configuration.py` | Exact vendor resource binding |
| `integrations/layout_parser/request.py` | Frozen detection adaptation request |
| `integrations/layout_parser/actionizer.py` | Vendor-to-domain adaptation |

All package initializers remain docstring-only ownership markers. Consumers use
direct imports from defining leaves.
