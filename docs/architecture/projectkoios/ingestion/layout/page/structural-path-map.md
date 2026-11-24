# Page-layout item-map structural path map

Status: proposed parallel ownership map. No source paths in the defining-path
column exist yet. The current paths remain authoritative until a separately
authorized cutover.

## Current-to-candidate ownership

| Current path or responsibility | Proposed defining path | Candidate owner |
|---|---|---|
| `_Item` in `layout/analysis.py` | `layout/page/item/definition.py` | One exact source-bound `ItemLayout` and its per-item geometry |
| raw `list[_Item]` and `tuple[_Item, ...]` collections in `layout/analysis.py` | `layout/page/item/inventory.py` | Complete ordered/keyed `ItemLayoutInventory` and collection geometry |
| `_PreparedPage` in `layout/analysis.py` | `layout/page/definition.py` | Exact page binding and complete candidate page-layout state |
| `LayoutGeometryContract._geometric_key` | `layout/page/item/definition.py` | Constructed `ItemLayout` geometry-order key |
| `LayoutGeometryContract._vertical_overlap_ratio` | `layout/page/item/definition.py` | Overlap between two constructed compatible item layouts |
| `LayoutGeometryContract._horizontal_extent` | `layout/page/item/inventory.py` | Extent of one constructed bounded item-layout selection |
| `LayoutGeometryContract._number` | typed numeric fields in `layout/page/item/definition.py` and `layout/page/definition.py` | Canonical serializer owns numeric encoding; no string-format helper |
| `LayoutGeometryContract._box_text` | typed bounding-box field in `layout/page/item/definition.py` | `ItemLayout` owns box validation; canonical serializer owns encoding |
| parallel `raw_blocks`, `input_text_blocks`, `non_text_block_ids`, `proposed_order`, and `exclusions` relations in `layout/contracts.py` | `layout/page/item/definition.py` and `layout/page/item/inventory.py` | One total layout disposition per exact page-item key |
| large page-level cross-collection reconstruction in `PageLayoutResult.__post_init__` | `layout/page/definition.py` | Page-level binding over already validated source and layout inventories |
| implicit JSON/dataclass projection | `layout/page/codec.py` | Strict canonical persisted map and nominal owner reconstruction |
| generic layout failures for candidate map construction | `layout/page/error.py` | Candidate page-layout contract and limit failures |

## Upstream source-owner dependency

The source owner decision is frozen: `Page` owns `PageItemInventory`. Those
source types are not assigned to `layout/page/`; their parallel design is
mirrored under [`documents/page/`](../../documents/page/index.md). The current
input remains `ExtractedPage` plus exact ordered `ExtractedBlock` values until
separate source Page implementation and cutover.

## Proposed source hierarchy

```text
src/python/projectkoios/ingestion/layout/page/
├── __init__.py                 # docstring-only ownership marker
├── definition.py               # PageLayout
├── codec.py                    # strict canonical persisted map codec
├── error.py                    # page-layout candidate failures
└── item/
    ├── __init__.py             # docstring-only ownership marker
    ├── definition.py           # ItemLayout
    ├── disposition.py          # item layout/geometry status enums
    └── inventory.py            # ordered persisted ItemLayout map
```

This documentation mirrors that hierarchy under:

```text
docs/architecture/projectkoios/ingestion/layout/page/
├── index.md
├── implementation.md
├── schematic.md
└── structural-path-map.md
```

## Current paths retained during the parallel build

| Current path | Retained authority |
|---|---|
| `layout/contracts.py` | Current requests, configuration, `LayoutBlockReference`, `PageLayoutResult`, groups, exclusions, and stable identities |
| `layout/analysis.py` | Current deterministic layout algorithm and authoritative page results |
| `layout/actionizer.py` | Current action contract |
| `layout/__init__.py` | Existing published compatibility facade |
| current consumers of `PageLayoutResult` | Current production behavior until explicit adoption and cutover |

The parallel candidate must not rewrite, alias, or silently decode these current
contracts.

## Candidate additions deferred from this design slice

The following paths require a separately bounded implementation request after
the value and inventory contracts are frozen:

| Candidate responsibility | Possible mirrored path | Reason deferred |
|---|---|---|
| complete candidate action request | `layout/page/projection/request.py` | Depends on frozen source-page and configuration binding |
| deterministic candidate actionizer | `layout/page/projection/actionizer.py` | Depends on frozen `ItemLayout` and inventory behavior |
| candidate action result | `layout/page/projection/result.py` | Must distinguish action execution identity from `PageLayout` evidence identity |
| parallel comparison request | `layout/page/comparison/request.py` | Depends on exact current/candidate result contracts |
| parallel comparison actionizer | `layout/page/comparison/actionizer.py` | Comparison semantics must be frozen separately |
| parallel comparison result | `layout/page/comparison/result.py` | Comparison evidence grants no cutover authority |
| disk runtime and store | `integrations/disk/layout/page/` | Runtime roots and private storage remain outside semantic identity |

No empty package or placeholder source module should be created before its
owner contract is implemented.

## Explicit non-moves

The candidate does not move behavior:

- from static methods to module functions;
- from static methods to an empty-constructor class;
- into `Page` when the behavior belongs to the derived layout channel;
- into `PageLayout` when it belongs to one item or the item inventory;
- into a generic base geometry contract; or
- into Workflow, Search, publication, or storage owners.

The final defining path is selected by constructed semantic state, not by
filename token order.
