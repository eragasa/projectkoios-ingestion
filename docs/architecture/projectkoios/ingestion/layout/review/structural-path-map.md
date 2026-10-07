# Layout review structural path map

The branch initially placed several provisional contracts under review. Human
semantic review corrected those paths before publication:

| Previous provisional path | New defining path | Ownership |
|---|---|---|
| `layout/review/evidence/render.py` | `layout/render/evidence.py` | Exact rendered-page identity |
| proposal symbols in `layout/review/kind.py` | `layout/proposal/kind.py` | Backend-neutral region taxonomy |
| `layout/review/evidence/source.py` | `layout/proposal/source.py` | Detector and model resource identity |
| `layout/review/proposal.py` | `layout/proposal/region.py` | Unaccepted region proposal |
| none | `layout/proposal/limits/definition.py` | Proposal count bounds |
| none | `layout/proposal/limits/error.py` | Proposal limit failure |
| none | `layout/review/configuration.py` | Review thresholds and bounds |
| none | `layout/review/request.py` | Complete comparison request |
| none | `layout/review/overlap.py` | Native-block/region overlap evidence |
| none | `layout/review/actionizer.py` | Deterministic review preparation |
| none | `layout/review/result.py` | Prepared review case |
| none | `layout/annotation/kind.py` | Human outcome and failure taxonomy |
| none | `layout/annotation/region.py` | Corrected region and block membership |
| none | `layout/annotation/order.py` | Corrected reading-order edge |
| none | `layout/annotation/failure.py` | Observed failure label |
| none | `layout/annotation/collection.py` | Complete human annotation evidence |
| none | `layout/annotation/limits/definition.py` | Annotation collection bounds |
| none | `layout/annotation/limits/error.py` | Annotation limit failure |
| none | `layout/validation/value.py` | Shared layout value validation |
| none | `layout/limits/definition.py` | Shared layout value bounds |
| none | `integrations/layout_parser/detection.py` | Frozen vendor detection record |
| none | `integrations/layout_parser/configuration.py` | Exact vendor resource binding |
| none | `integrations/layout_parser/request.py` | Frozen detection adaptation request |
| none | `integrations/layout_parser/actionizer.py` | Vendor-to-domain adaptation |
| none | `integrations/layout_parser/result.py` | Adapted proposal result |

All introduced package initializers are docstring-only ownership markers. No
compatibility re-export façade is introduced.
