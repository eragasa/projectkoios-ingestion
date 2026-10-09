# Docling integration structural path map

| Semantic owner | Defining path |
| --- | --- |
| Candidate actionizer | `integrations/docling/layout/reading/actionizer.py` |
| Ordered candidate, neutral elements, inventory, and producer evidence | `layout/reading/order/candidate.py` |
| Pinned runtime configuration | `integrations/docling/layout/reading/configuration.py` |
| Direction, status, and failure taxonomy | `integrations/docling/layout/reading/kind.py` |
| Hard bounds | `integrations/docling/layout/reading/limits.py` |
| Provider port and installed implementation | `integrations/docling/layout/reading/provider.py` |
| Immutable candidate request | `integrations/docling/layout/reading/request.py` |
| Immutable candidate result | `integrations/docling/layout/reading/result.py` |

This hierarchy is additive. It does not move or alias canonical layout,
annotation, COCO, or page-projection contracts.
