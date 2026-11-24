# Page-layout item-map schematic

## Semantic ownership

```mermaid
classDiagram
    direction LR

    class Page {
        +page_id
        +PageItemInventory items
    }

    class PageItemInventory {
        +inventory_id
        +item_order
        +page_item_by_id
        +require(item_id)
    }

    class PageItem {
        +item_id
        +source_ordinal
        +source_kind
        +source_evidence_reference
    }

    class PageLayout {
        +page_id
        +page_item_inventory_id
        +ItemLayoutInventory items
        +groups
        +warnings
        +page_kind
        +confidence
    }

    class ItemLayoutInventory {
        +inventory_id
        +item_order
        +item_layout_by_id
        +require(item_id)
        +layout_order()
        +horizontal_extent()
        +overlap_pairs()
        +partition()
    }

    class ItemLayout {
        +item_layout_id
        +page_id
        +item_id
        +source_ordinal
        +source_kind
        +geometry_status
        +bounding_box
        +disposition
        +proposed_order_index
        +group_id
        +exclusion_id
        +geometry_order_key()
        +vertical_overlap(other)
    }

    Page *-- PageItemInventory
    PageItemInventory *-- PageItem
    PageLayout *-- ItemLayoutInventory
    ItemLayoutInventory *-- ItemLayout
    PageLayout --> Page : exact immutable identity binding
    ItemLayout --> PageItem : exact item_id binding
```

The constructors require exact key and source-order equality:

```mermaid
flowchart LR
    PageKeys[Page.items.keys]
    LayoutKeys[PageLayout.items.keys]
    PageOrder[Page.items.order]
    LayoutOrder[PageLayout.items.order]
    KeyEquality{exactly equal}
    OrderEquality{exactly equal}

    PageKeys --> KeyEquality
    LayoutKeys --> KeyEquality
    PageOrder --> OrderEquality
    LayoutOrder --> OrderEquality
```

No module helper or empty-constructor service sits between these owners.

## Parallel build

```mermaid
flowchart TD
    Page[Exact source Page]
    Config[Exact layout configuration]

    Current[Current deterministic path]
    Candidate[Candidate page-layout path]

    CurrentResult[PageLayoutResult<br/>current authoritative layout evidence]
    CandidateResult[PageLayout<br/>parallel non-authoritative candidate]

    Compare[ParallelLayoutComparison<br/>keys and source order<br/>item dispositions<br/>proposed order<br/>groups and exclusions<br/>warnings and page status]
    Replay[Deterministic replay evidence]
    Gate{Explicit coordinated cutover decision}
    Retain[Retain current authority]
    Cutover[Separately authorized cutover]

    Page --> Current
    Config --> Current
    Page --> Candidate
    Config --> Candidate
    Current --> CurrentResult
    Candidate --> CandidateResult
    CurrentResult --> Compare
    CandidateResult --> Compare
    Compare --> Replay
    Replay --> Gate
    Gate -->|not authorized| Retain
    Gate -->|separately authorized| Cutover
```

Successful comparison and replay do not take the cutover edge automatically.

## Persistence and loading

```mermaid
sequenceDiagram
    participant Store as Canonical private store
    participant Codec as PageLayout codec
    participant Item as ItemLayout constructors
    participant Inventory as ItemLayoutInventory constructor
    participant PageOwner as Exact Page owner
    participant Layout as PageLayout constructor

    Store->>Codec: canonical payload bytes
    Codec->>Codec: reject duplicate or unknown JSON keys
    Codec->>Item: bounded item-layout values
    Item-->>Codec: nominal ItemLayout values
    Codec->>Inventory: item_order + item_layout_by_id
    Inventory->>Inventory: validate keys, values, uniqueness, order
    Inventory-->>Codec: nominal ItemLayoutInventory
    Codec->>PageOwner: resolve exact page_item_inventory_id
    PageOwner-->>Codec: nominal Page and PageItemInventory
    Codec->>Layout: exact page + item-layout inventory
    Layout->>Layout: require total key and source-order equality
    Layout->>Layout: verify all stable identities
    Layout-->>Codec: nominal PageLayout
```

The persisted map and order are semantic. Runtime hash buckets, hash seeds, and
capacity are not.

## Authority boundary

```mermaid
flowchart LR
    Page[Page<br/>authoritative source-page evidence]
    Current[PageLayoutResult<br/>current authoritative layout evidence]
    Candidate[PageLayout<br/>parallel candidate evidence]
    Comparison[ParallelLayoutComparison<br/>deterministic comparison evidence]
    Decision{Explicit coordinated cutover}
    Authority[Candidate becomes authoritative]

    Page --> Current
    Page --> Candidate
    Current --> Comparison
    Candidate --> Comparison
    Comparison --> Decision
    Decision -->|separately authorized| Authority
```

No design, construction, comparison, or replay edge authorizes cutover,
publication, Search admission, or release.
