# Source Page item-map structural path map

Status: proposed parallel ownership map. No candidate source path listed below
exists yet. Current `models.py` contracts remain authoritative until explicit
cutover.

## Current-to-candidate ownership

| Current path or responsibility | Proposed defining path | Candidate owner |
|---|---|---|
| `ExtractedPage` in `models.py` | `documents/page/definition.py` | Source Page metadata and exact `PageItemInventory` binding |
| raw `ExtractedPage.blocks` tuple | `documents/page/item/inventory.py` | Ordered persisted page-item map and keyed lookup |
| page-block identity and evidence in `ExtractedBlock` | retained exact nominal `ExtractedBlock` value | One complete source Page item without wrapper or evidence loss |
| ad hoc `block_id -> ExtractedBlock` dictionaries in consumers | `documents/page/item/inventory.py` | Owner-native keyed lookup |
| inferred page item order from tuple position | `documents/page/item/inventory.py` | Explicit persisted `item_order` and source ordinal validation |
| implicit dataclass/JSON projection | `documents/page/codec.py` | Strict canonical source Page reconstruction |
| generic construction failures | `documents/page/error.py` | Source Page and item-inventory contract failures |

## Proposed source hierarchy

```text
src/python/projectkoios/ingestion/documents/page/
├── __init__.py                 # retained docstring-only ownership marker
├── base.py                     # retained nominal page boundary
├── definition.py               # candidate Page
├── codec.py                    # strict canonical Page payload codec
├── error.py                    # source Page contract failures
└── item/
    ├── __init__.py             # docstring-only ownership marker
    └── inventory.py            # PageItemInventory of exact ExtractedBlock values
```

This documentation mirrors that hierarchy under:

```text
docs/architecture/projectkoios/ingestion/documents/page/
├── index.md
├── implementation.md
├── schematic.md
└── structural-path-map.md
```

## Current paths retained during the parallel build

| Current path | Retained authority |
|---|---|
| `models.py:ExtractedBlock` | Current exact extracted source-item evidence and item identity |
| `models.py:ExtractedPage` | Current source page metadata and native block order |
| `models.py:ExtractedDocument` | Current ordered page collection and source binding |
| `cache.py` current codecs | Current persisted extraction cache behavior |
| current extraction adapters | Current `ExtractedPage` and `ExtractedBlock` production |
| current consumers | Current source behavior until explicit adoption and cutover |

The candidate does not alias, mutate, or silently reinterpret these current
contracts.

## Candidate additions deferred from this design slice

| Candidate responsibility | Possible mirrored path | Reason deferred |
|---|---|---|
| candidate Page projection request | `documents/page/projection/request.py` | Exact current-source binding and limits must be frozen |
| candidate Page projection actionizer | `documents/page/projection/actionizer.py` | Depends on frozen Page and item inventory contracts |
| candidate Page projection result | `documents/page/projection/result.py` | Must distinguish action identity from Page evidence identity |
| current/candidate comparison request | `documents/page/comparison/request.py` | Depends on both frozen contracts |
| deterministic comparison actionizer | `documents/page/comparison/actionizer.py` | Exact evidence-equivalence profile requires separate review |
| comparison result | `documents/page/comparison/result.py` | Grants no source cutover authority |
| private disk runtime and store | `integrations/disk/documents/page/` | Runtime roots remain outside semantic identity |

No empty package or placeholder module is created before its owner contract is
implemented.

## Explicit non-moves

The source owner decision means:

- `layout/page/` does not define `PageItem`, `PageItemInventory`, source item
  order, or source item identity;
- storage integrations do not define semantic Page identity;
- generic `AbstractDocumentPage` does not retain text-only requirements merely
  to accept the candidate; a separately implemented `AbstractTextDocumentPage`
  owns ordered block identities and canonical text;
- Page item behavior does not move to module helpers, static methods, or an
  empty-constructor utility object; and
- current IDs do not become candidate IDs through aliases.

The final source paths must be justified by constructed state and invariants,
not by mechanical relocation from `models.py`.
