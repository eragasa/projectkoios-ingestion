# Source Page item-map schematic

## Source ownership

```mermaid
classDiagram
    direction LR

    class Page {
        +page_id
        +source_id
        +source_blob_id
        +page_index
        +width
        +height
        +coordinate_system
        +rotation_degrees
        +PageItemInventory items
    }

    class PageItemInventory {
        +inventory_id
        +page_id
        +item_order
        +page_item_by_id
        +require(item_id)
        +source_order()
    }

    class ExtractedBlock {
        +block_id as item_id
        +kind
        +source_spans
        +text
        +asset_identity
        +warning_ids
        +extraction_method
        +confidence
    }

    class PageLayout {
        +page_id
        +page_item_inventory_id
        +ItemLayoutInventory items
    }

    Page *-- PageItemInventory
    PageItemInventory *-- ExtractedBlock : exact PageItem values
    PageLayout --> Page : exact immutable identity binding
    PageLayout --> PageItemInventory : exact key and source-order binding
```

`Page` owns source items. `PageLayout` owns only derived item-layout evidence.

## Parallel source build

```mermaid
flowchart TD
    Extraction[Exact authorized extraction evidence]
    Current[Current source path]
    Candidate[Candidate source Page path]
    ExtractedPage[ExtractedPage<br/>current authoritative source page]
    Page[Page and PageItemInventory<br/>parallel candidate source evidence]
    Compare[PageParallelComparison<br/>source and blob identity<br/>page identity<br/>item keys and native order<br/>complete retained evidence]
    Replay[Deterministic replay evidence]
    Gate{Explicit coordinated source cutover}
    Retain[Retain current authority]
    Cutover[Separately authorized source cutover]

    Extraction --> Current
    Extraction --> Candidate
    Current --> ExtractedPage
    Candidate --> Page
    ExtractedPage --> Compare
    Page --> Compare
    Compare --> Replay
    Replay --> Gate
    Gate -->|not authorized| Retain
    Gate -->|separately authorized| Cutover
```

## Candidate layout consumption

```mermaid
sequenceDiagram
    participant Store as Canonical private Page store
    participant Codec as Page codec
    participant Inventory as PageItemInventory constructor
    participant PageOwner as Page constructor
    participant Layout as Candidate page-layout action

    Store->>Codec: canonical Page payload bytes
    Codec->>Codec: reject duplicate and unknown JSON keys
    Codec->>Inventory: page identity + item_order + page_item_by_id
    Inventory->>Inventory: validate exact source/page binding and order
    Inventory-->>Codec: nominal PageItemInventory
    Codec->>PageOwner: exact page metadata + nominal inventory
    PageOwner->>PageOwner: verify Page and inventory identities
    PageOwner-->>Codec: nominal Page
    Codec-->>Layout: nominal Page, never decoded private JSON
    Layout->>Layout: require exact page and item inventory identities
```

## Authority boundary

```mermaid
flowchart LR
    Current[ExtractedPage<br/>current authoritative source evidence]
    Candidate[Page<br/>parallel candidate source evidence]
    Comparison[PageParallelComparison<br/>comparison evidence only]
    Decision{Explicit coordinated cutover}
    Authority[Candidate Page becomes authoritative]

    Current --> Comparison
    Candidate --> Comparison
    Comparison --> Decision
    Decision -->|separately authorized| Authority
```

Construction, persistence, loading, comparison, and replay do not themselves
authorize source cutover or downstream layout cutover.
