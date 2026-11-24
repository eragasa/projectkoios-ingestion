# Page and page-layout item-map design

Status: design candidate for a parallel build. The existing
`PageLayoutResult` remains authoritative. This design is not called `v2`, does
not mutate current records or stable identities, and grants no cutover,
publication, Search, or release authority.

## Problem

The current contract correctly validates its evidence, but one page item's
layout state is distributed across several parallel collections:

- `raw_blocks`;
- `input_text_blocks`;
- `non_text_block_ids`;
- `proposed_order`;
- `exclusions`; and
- group membership.

`PageLayoutResult.__post_init__` must repeatedly reconstruct the relation among
those collections. Geometry behavior that lacks a constructed owner is grouped
under `LayoutGeometryContract` as static methods.

The parallel candidate normalizes the relation into one exact source item and
one exact layout disposition per page-item identity.

## Authority and channel boundary

`Page` and `PageLayout` remain separate immutable channels.

- `Page` owns extractor-native page items and their native order.
- `PageLayout` owns a derived layout disposition for every exact page item.
- `PageLayout` references the source page and source-item inventory by immutable
  identity; it does not mutate or replace them.
- Layout order does not replace extractor-native item order.
- Geometry unavailability, exclusion, and non-text status are explicit
  dispositions rather than omissions.
- A candidate parallel result is comparison evidence only until explicit
  cutover.

The current authoritative `PageLayoutResult` continues to feed existing
consumers throughout the parallel build.

## Semantic model

```text
Page
└── items: PageItemInventory
    ├── order: tuple[item_id, ...]
    └── by_id: item_id -> PageItem

PageLayout
├── page_id
├── page_item_inventory_id
└── items: ItemLayoutInventory
    ├── order: tuple[item_id, ...]
    └── by_id: item_id -> ItemLayout
```

The maps have exactly the same keys and exact source order:

```text
Page.items.keys == PageLayout.items.keys
Page.items.order == PageLayout.items.order
```

The source map is authoritative for page-item content. The layout map is the
single source of truth inside one candidate result, while the candidate result
itself remains non-authoritative relative to the current layout channel.

## `PageItemInventory`

The source page-item inventory is an immutable identity projection of the exact
page items. During the parallel build, each item corresponds to one retained
extractor-native block identity and ordinal. It owns:

- source page identity;
- native item order;
- unique item identity validation;
- bounded item count;
- keyed item lookup; and
- a stable inventory identity over ordered item identities.

The candidate must not duplicate or normalize source text, images, spans, or
other evidence into layout-owned payloads. It retains exact references to their
source owners.

## `ItemLayout`

`ItemLayout` is a non-trivially constructed value bound to one exact page item.
It contains the minimum complete layout disposition for that item:

- `page_id` and `item_id`;
- source ordinal and source item kind;
- geometry status and an optional validated bounding box;
- layout disposition;
- optional proposed-order index;
- optional group identity; and
- optional exclusion identity.

Initial candidate dispositions are:

- `ordered_text`;
- `excluded_text`;
- `non_text`; and
- `geometry_unavailable`.

The exact enum is frozen only with the implementation request. The contract
must distinguish a source non-text item from a text item whose geometry cannot
support layout analysis.

`ItemLayout` owns operations that require one constructed item, including:

- its deterministic geometry-order key;
- width and height of available geometry;
- vertical overlap with another `ItemLayout` bound to the same page and
  coordinate system; and
- validation of order, group, exclusion, and disposition consistency.

It does not own collection partitions or page-level confidence.

## `ItemLayoutInventory`

`ItemLayoutInventory` is the non-trivially constructed semantic map over a
bounded complete page. It persists both source order and keyed entries. It owns:

- exact key and source-order equality with `PageItemInventory`;
- unique key and unique layout-entry identity validation;
- keyed `require(item_id)` lookup;
- source-ordered iteration;
- layout-order projection;
- horizontal extent over a bounded selected inventory;
- overlap-pair detection;
- vertical-support calculations; and
- bounded partitions such as ordered, excluded, non-text, wide, narrow, left,
  right, spanning, and bottom candidates.

A partition returns another semantic inventory or an explicitly typed
selection. It does not return an unowned raw list as a new behavioral boundary.

The inventory is the owner that replaces collection-oriented static geometry
methods. Per-item geometry remains on `ItemLayout`.

## `PageLayout`

`PageLayout` binds:

- exact source, blob, page, coordinate-system, rotation, and page dimensions;
- exact `PageItemInventory` identity;
- complete `ItemLayoutInventory`;
- group hypotheses;
- warning evidence;
- page-kind disposition;
- confidence;
- processor and configuration identities; and
- its own stable result identity.

It owns page-level completeness and cross-record validation. It does not
recompute item geometry that belongs to `ItemLayout` or collection algorithms
that belong to `ItemLayoutInventory`.

## Persisted logical maps

The semantic maps are persisted. Python dictionary buckets, hash seeds,
capacity, and other runtime implementation details are not.

A candidate canonical representation is:

```json
{
  "page_id": "...",
  "page_item_inventory_id": "...",
  "item_order": ["item:a", "item:b"],
  "item_layout_by_id": {
    "item:a": {
      "page_id": "...",
      "item_id": "item:a",
      "item_layout_id": "...",
      "source_ordinal": 0,
      "source_kind": "text",
      "geometry_status": "available",
      "bounding_box": [10.0, 20.0, 30.0, 40.0],
      "disposition": "ordered_text",
      "proposed_order_index": 0,
      "group_id": "...",
      "exclusion_id": null
    },
    "item:b": {
      "page_id": "...",
      "item_id": "item:b",
      "item_layout_id": "...",
      "source_ordinal": 1,
      "source_kind": "image",
      "geometry_status": "available",
      "bounding_box": [40.0, 20.0, 60.0, 40.0],
      "disposition": "non_text",
      "proposed_order_index": null,
      "group_id": null,
      "exclusion_id": null
    }
  }
}
```

The example is illustrative, not a frozen wire contract.

The codec must reject duplicate JSON keys before construction. The owner
constructor then requires:

- every `item_order` value is a canonical bounded identity;
- `item_order` is unique;
- map keys exactly equal `item_order` as a set;
- every map key equals the contained `ItemLayout.item_id`;
- every source item has exactly one layout disposition;
- no unknown item is present; and
- no item layout contradicts its disposition.

Canonical JSON sorts object keys, but source order comes only from
`item_order`. Map iteration order never establishes semantic order.

## Runtime index

The owner may reconstruct a private runtime hash table for bounded lookup. That
index is derived from the persisted logical map and cannot contribute new
semantic state. Public operations expose owner-native methods such as
`require(item_id)` and typed selection, not a mutable dictionary.

## Identity profile

Candidate identity material is independent of runtime paths and Python hashes.

- `PageItemInventory` hashes ordered source item identities.
- `ItemLayout` hashes every persisted field that can change its disposition,
  geometry, order, or lineage.
- `ItemLayoutInventory` hashes ordered `(item_id, item_layout_id)` pairs.
- `PageLayout` hashes exact page/source identity, source item inventory identity,
  item-layout inventory identity, groups, warnings, page status, processor, and
  configuration identity.

Map keys and contained `item_id` values are both validated even though the
stable inventory preimage needs only one canonical ordered representation.
Redundant persisted representations never create two independent sources of
truth.

## Ownership progression

Smell reduction moves only in this direction:

```text
private dangling function
    -> public dangling function
    -> static class method
    -> instance method on an empty-constructor class
    -> instance method on a semantically non-trivial constructed owner
```

The parallel design targets the final state directly. A constructor is not an
owner merely because it accepts a dummy value: its validated state and
invariants must be used by the behavior.

The design therefore rejects moving `LayoutGeometryContract` methods to module
functions or to another empty service object.

## Parallel build and cutover boundary

The candidate is built beside the current contract:

```text
exact source Page
    ├── current DeterministicLayoutProcessor -> PageLayoutResult
    └── candidate page-layout action         -> PageLayout
```

Both branches receive the same authorized source page and configuration. The
candidate does not read private serialized `PageLayoutResult` JSON to construct
its owner types; it consumes exact owner-native inputs.

Parallel evidence must record:

- source page and item inventory identities;
- current result identity;
- candidate result identity;
- exact item-key and source-order equality;
- per-item disposition comparison;
- proposed-order comparison;
- group, exclusion, warning, confidence, and page-kind comparison; and
- any intentional semantic difference.

Cutover is a separate human and coordination boundary. It requires explicit
consumer-adoption and replay evidence. Passing parallel comparison does not by
itself authorize replacement, release, publication, or removal of the current
contract.

## Upstream page-owner dependency

`Page` and `PageItemInventory` are source owners, not layout-owned types. The
owner decision is frozen: the source Page owner introduces the immutable
`PageItemInventory`. The mirrored source-owner design is documented under
[`documents.page`](../../documents/page/index.md).

The current implementation supplies source evidence through `ExtractedPage` and
its exact ordered blocks. During the parallel build, `layout.page` receives the
nominal candidate Page and exact item inventory; it does not project a private
substitute, copy source payload ownership, or derive source identities from
serialized `PageLayoutResult` JSON.

## Proposed defining paths

The documentation mirrors the proposed layout ownership hierarchy:

```text
projectkoios/ingestion/layout/page/
├── definition.py
├── codec.py
├── error.py
└── item/
    ├── definition.py
    ├── disposition.py
    └── inventory.py
```

Package initializers remain docstring-only ownership markers. Consumers import
defining leaves directly. The paths are proposed; no source package is created
by this design-only slice.

## Rejected designs

The design rejects:

- moving static methods to private or public module helpers;
- replacing static methods with instance methods on an empty constructor;
- exposing raw mutable dictionaries;
- using runtime hash order as source or layout order;
- persisting only a map while silently inferring source order;
- omitting non-text or unavailable-geometry items from the layout map;
- storing the same semantic fact in several independently mutable collections;
- changing current `PageLayoutResult` identities during the parallel build;
- calling the candidate `v2` before cutover;
- compatibility aliases that hide which contract a consumer uses; and
- inferring cutover authority from successful replay.

## Validation plan

Before implementation can be considered complete, evidence must cover:

- empty, one-item, and maximum-bound inventories;
- duplicate, missing, unknown, reordered, and cross-page item identities;
- map-key/value identity disagreement;
- every disposition and invalid field combination;
- missing, non-positive, out-of-page, and non-finite geometry;
- deterministic keyed lookup and source-order iteration;
- horizontal extent, overlap, support, and partition behavior;
- canonical JSON with adversarial key order and duplicate-key rejection;
- byte-identical candidate replay;
- exact parallel comparison against representative current results;
- mutation tests for map completeness and stable-ID fields;
- no private/public dangling helpers, static utility containers, or empty
  constructor owners in the candidate scope; and
- focused tests, full tests, strict type checking, formatting, Ruff, smell
  gates, documentation links, and clean-wheel direct imports.
