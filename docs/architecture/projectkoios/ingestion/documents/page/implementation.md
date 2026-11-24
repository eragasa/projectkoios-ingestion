# Source Page and item-inventory design

Status: source-owner design candidate for a parallel build. The current
`ExtractedPage.blocks` tuple remains authoritative. This design introduces no
alias, current-schema mutation, cutover, publication, or release authority.

## Owner decision

The source Page owner defines `PageItemInventory`.

`layout.page` may consume the exact nominal inventory, but it may not derive a
private substitute, decode a serialized Page payload itself, or redefine page
item order. This decision makes the Page-to-PageLayout key relation an exact
owner boundary rather than a layout convention.

## Current boundary

The current source contracts are:

- `ExtractedPage` in `models.py`;
- the exact ordered `ExtractedPage.blocks` tuple; and
- `ExtractedBlock.block_id` as the retained item identity.

The parallel Page is produced from the same authorized extraction evidence. It
does not replace or mutate current extraction objects during the parallel
build.

## Semantic model

```text
Page
├── page_id
├── exact source/page metadata
└── items: PageItemInventory
    ├── inventory_id
    ├── order: tuple[item_id, ...]
    └── by_id: item_id -> PageItem
```

The initial parallel build uses the exact nominal `ExtractedBlock` as the
`PageItem` value. It does not introduce a wrapper or copy selected fields into a
new item type. This preserves text, asset, mask, span, warning,
extraction-method, confidence, and stable block identity evidence without a
second item contract. Moving `ExtractedBlock` to a different owner is a separate
future boundary and is not required for the Page inventory.

## `PageItemInventory`

`PageItemInventory` is a non-trivially constructed immutable semantic map. Its
constructor binds:

- exact source identity and source blob identity;
- exact page identity and physical page index;
- a bounded source-ordered item sequence; and
- a keyed value for every ordered item identity.

It owns:

- unique item identity validation;
- exact source and page membership validation;
- native source order;
- keyed `require(item_id)` lookup;
- source-ordered iteration;
- bounded count and retained-size validation; and
- stable inventory identity.

The inventory does not own layout order, layout groups, exclusions, OCR,
normalized transcript text, or Search chunks.

## Persisted logical map

The Page payload persists both native order and keyed source items:

```json
{
  "page_id": "...",
  "source_id": "...",
  "source_blob_id": "...",
  "page_index": 0,
  "item_order": ["item:a", "item:b"],
  "page_item_by_id": {
    "item:a": {
      "item_id": "item:a",
      "source_ordinal": 0,
      "kind": "text",
      "source_evidence": "..."
    },
    "item:b": {
      "item_id": "item:b",
      "source_ordinal": 1,
      "kind": "image",
      "source_evidence": "..."
    }
  }
}
```

The example is illustrative, not a frozen wire contract. The complete
implementation must retain exact source evidence rather than the abbreviated
`source_evidence` placeholders shown here.

The codec rejects duplicate or unknown JSON keys before construction. The
constructor then requires:

- unique, bounded canonical item identities;
- exact equality between `item_order` and map keys;
- equality between every map key and contained item identity;
- equality between every source ordinal and its `item_order` position;
- exact source/blob/page binding for every retained source span;
- no missing or unknown source item; and
- exact current `ExtractedPage.blocks` order during parallel comparison.

Canonical JSON object-key order does not establish native item order.
`item_order` is the sole persisted ordering authority.

## Runtime lookup

The owner may reconstruct a private runtime hash table from the persisted map.
Runtime buckets, capacity, and Python hash values are not semantic state. The
public contract exposes owner methods such as `require(item_id)` and ordered
iteration rather than a mutable dictionary.

## Page identity and inventory identity

Candidate identity material is independent of runtime paths and Python hashes.

- Page identity binds exact source, blob, and physical page identity.
- Item identity remains the exact source-owner item identity.
- Inventory identity hashes ordered `(item_id, page_item_identity)` pairs.
- Page result identity binds page metadata and the exact item inventory
  identity.

The implementation request must freeze identity namespaces and canonical
preimages before any candidate artifact is produced. Parallel identities do not
replace current IDs.

## Relation to `AbstractDocumentPage`

`documents/page/base.py` currently defines a nominal `AbstractDocumentPage`
with `document_page_id`, ordered block identities, and canonical text. Those
last two requirements are text-page semantics, not invariants of every generic
source Page. The parallel Page must not fabricate canonical page text merely to
satisfy that base.

The parallel design therefore freezes this hierarchy correction before Page
implementation:

- `AbstractDocumentPage` owns only generic page identity and page metadata;
- `AbstractTextDocumentPage(AbstractDocumentPage)` owns ordered block identities
  and canonical text;
- `AbstractTranscriptPage` moves to `AbstractTextDocumentPage`; and
- the candidate `Page` may implement `AbstractDocumentPage` without acquiring
  fabricated text semantics.

This is a separately bounded owner correction, not an in-place change authorized
by this documentation checkpoint. Until that correction is implemented, current
nominal bases and consumers remain authoritative. A compatibility inheritance
claim is not allowed to invent joined text or drop non-text items.

## Parallel construction and comparison

```text
exact current ExtractedPage
    ├── retained current path -> ExtractedPage.blocks
    └── candidate source path -> Page(PageItemInventory)
```

Parallel comparison records:

- source, blob, and physical page identity;
- current block identities and order;
- candidate item identities and order;
- exact item count and key equality;
- exact source evidence retained per item;
- current and candidate inventory/result identities; and
- any intentional semantic difference.

The candidate layout path consumes only the nominal candidate Page and
`PageItemInventory`, never private Page JSON.

## Proposed defining paths

The documentation mirrors the proposed source ownership hierarchy:

```text
projectkoios/ingestion/documents/page/
├── base.py                     # retained nominal page boundary
├── definition.py               # candidate Page
├── codec.py                    # strict canonical Page payload
├── error.py                    # Page and inventory contract failures
└── item/
    ├── __init__.py             # docstring-only ownership marker
    └── inventory.py            # PageItemInventory of exact ExtractedBlock values
```

The paths are proposed. This design-only slice creates no source package or
placeholder module.

## Rejected designs

The source Page design rejects:

- letting `layout.page` invent or own source item identity/order;
- exposing `ExtractedPage.blocks` as a public raw tuple in the candidate;
- retaining only a map and inferring order from object keys;
- persisting order and map without cross-validation;
- copying only geometry while dropping exact source item evidence;
- fabricating canonical page text to satisfy a nominal base;
- moving inventory behavior to module helpers, static methods, or an
  empty-constructor service;
- changing current `ExtractedPage` or `ExtractedBlock` identities during the
  parallel build; and
- inferring cutover authority from equality on a limited fixture set.

## Validation plan

Before source Page implementation is complete, evidence must cover:

- empty, one-item, and exact maximum-bound pages;
- duplicate, missing, unknown, reordered, and cross-page item identities;
- map-key/value and source-ordinal disagreement;
- source/blob/page disagreement in retained spans;
- exact retention of text, asset, mask, warning, extraction-method, confidence,
  and source-span evidence;
- canonical JSON with adversarial object-key order and duplicate-key rejection;
- deterministic keyed lookup and native-order iteration;
- stable identity mutation tests;
- byte-identical candidate replay;
- exact comparison with representative current `ExtractedPage` values;
- no dangling helpers, static utility containers, or empty-constructor owners
  in the candidate scope; and
- strict typing, formatting, Ruff, focused and full tests, smell gates,
  documentation links, and clean-wheel direct imports.
